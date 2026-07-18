from fastapi import FastAPI, HTTPException, Request
from app.config import settings
from app.schemas import ChatHistoryRequest, ChatAnalysisResponse, JobMatchRequest, JobMatchResponse
from app.services.vector_scan import vector_scanner
from app.services.llm_agent import LlmAgentService
from app.services.analyzer import rules_engine
from app.utils.helpers import clamp_score
from pydantic import BaseModel
from typing import List
import numpy as np
import requests
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import uvicorn
import traceback
import re
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


app = FastAPI(title = settings.APP_NAME, version = settings.VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public deployment runs against a free-tier Groq API key shared by every visitor —
# these limits keep the daily quota from being exhausted by one heavy user.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _reject_oversized_input(*texts: str) -> None:
    for text in texts:
        if len(text) > settings.MAX_INPUT_CHARS:
            raise HTTPException(
                status_code=400,
                detail=f"Input exceeds the {settings.MAX_INPUT_CHARS}-character limit for this demo."
            )


@app.post("/chat", response_model = ChatAnalysisResponse)
@limiter.limit("5/minute")
async def analyze_compliance_dialogue(request: Request, payload: ChatHistoryRequest):
    user_messages = [m.content for m in payload.history if m.role == "user"]
    if not user_messages:
        return ChatAnalysisResponse(
            agent_message = "I'm ready when you are. Please paste a job description or list your core responsibilities.",
            risk_score = 0,
            overall_risk_level = "Pending",
            requires_more_info = True,
            flags = []
        )
        
    latest_user_input = user_messages[-1]
    _reject_oversized_input(latest_user_input)

    risk_score, risk_level, requires_more, flags = vector_scanner.scan(
        latest_user_input
    )

    formatted_flags = [f"- Flagged User Sentence: '{f.matched_text}'\n  Reason: {f.reason}" for f in flags]
    flag_context = "\n".join(formatted_flags)

    pipeline_result = await LlmAgentService.run_optimization_pipeline(latest_user_input, flag_context)

    verdict = pipeline_result.get("verdict", "SAFE")
    explanation = pipeline_result.get("explanation", "")
    optimized_text = pipeline_result.get("optimized_text", "")

    if verdict == "SAFE":
        risk_score = 0
        risk_level = "Safe"
        flags = []
        requires_more = False
    elif verdict == "LOW_RISK":
        risk_score = clamp_score(risk_score, 10, 19)
        risk_level = "Low"
    elif verdict ==  "MEDIUM_RISK":
        risk_score = clamp_score(risk_score, 20, 44)
        risk_level = "Medium"
    elif verdict == "CRITICAL_HIGH_RISK":
        risk_score = max(risk_score, 85)
        risk_level = "Critical"

    agent_display_message = (
        f"{explanation}\n\n"
        f"AUTOMATICALLY OPTIMIZED PROFILE VERSION:\n"
        f"```text\n{optimized_text}\n```"
    )

    return ChatAnalysisResponse(
        agent_message = agent_display_message,
        risk_score = risk_score,
        overall_risk_level = risk_level,
        requires_more_info = requires_more,
        flags = flags
    )

@app.post("/match", response_model=JobMatchResponse)
@limiter.limit("5/minute")
async def match_and_optimize_profile(request: Request, payload: JobMatchRequest):
    """
    Two-stage pipeline: detection+scoring first, then a separate rewrite call
    that only ever sees the resume text (never the job description).
    """
    _reject_oversized_input(payload.candidate_profile, payload.job_description)

    _, _, _, semantic_flags = vector_scanner.scan(payload.candidate_profile)
    semantic_lines = [f"- Flagged Text Segment: '{f.matched_text}'\n Reason: {f.reason}" for f in semantic_flags]

    keyword_result = rules_engine(payload.candidate_profile)
    keyword_lines = [
        f"- Flagged Text Segment: '{f['matched_text']}'\n Reason: {f['reason']}"
        for f in keyword_result["flags"]
    ]

    all_flag_lines = semantic_lines + keyword_lines
    flag_context = "\n".join(all_flag_lines)

    computed_match_score = vector_scanner.compute_match_score(
        payload.candidate_profile, payload.job_description
    )
    print(f"DEBUG computed_match_score = {computed_match_score}")

    detection_result = await LlmAgentService.run_detection_pipeline(
        candidate_profile=payload.candidate_profile,
        job_description=payload.job_description,
        flag_context=flag_context,
        computed_match_score=computed_match_score
    )

    llm_score = detection_result.get("overall_match_score", computed_match_score)

    if abs(llm_score - computed_match_score) > 10:
        final_match_score = computed_match_score
    else:
        final_match_score = llm_score

    detected_gaps = detection_result.get("detected_gaps", [])
    # The small local model occasionally emits a placeholder gap with blank
    # detected_risk/optimization_strategy fields instead of real content — drop those.
    detected_gaps = [
        g for g in detected_gaps
        if g.get("detected_risk", "").strip() and g.get("optimization_strategy", "").strip()
    ]
    has_compliance_gap = any(g.get("category") == "Regulatory Compliance Risk" for g in detected_gaps)

    if not keyword_result["flags"]:
        # No literal supervisory/managerial word (managed/led/directed/oversaw) was
        # found. Semantic-only matches are noisy — they can fire at ~0.42-0.50
        # confidence on generic sentences with no real supervisory language — so they
        # aren't trusted as ground truth here. Strip any compliance gap the LLM
        # hallucinated from that noise.
        detected_gaps = [g for g in detected_gaps if g.get("category") != "Regulatory Compliance Risk"]
    elif not has_compliance_gap:
        # Pre-scan found a literal supervisory/managerial word (managed/led/directed/
        # oversaw), but the detection LLM failed to surface it. Keyword matches are a
        # precise, low-noise signal (unlike semantic-only matches, which can fire at
        # ~0.42-0.50 confidence on generic sentences with no real supervisory language),
        # so it's safe to synthesize the gap directly instead of trusting a small
        # model's inconsistent judgment call.
        if semantic_flags:
            matched_text = semantic_flags[0].matched_text
            alternative = semantic_flags[0].suggested_alternative
        else:
            matched_text = keyword_result["flags"][0]["matched_text"]
            alternative = keyword_result["flags"][0]["suggested_alternative"]

        detected_gaps.append({
            "category": "Regulatory Compliance Risk",
            "detected_risk": f"Your resume contains supervisory/managerial language (e.g., \"{matched_text}\") that may fall outside the individual-contributor scope typically required for this visa classification.",
            "optimization_strategy": f"Reframe this language around hands-on technical contribution rather than people management, for example: {alternative}."
        })

    optimized_profile = await LlmAgentService.run_rewrite_pipeline(
        candidate_profile=payload.candidate_profile,
        detected_gaps=detected_gaps
    )

    compliance_verdict = detection_result.get("compliance_verdict", "SAFE")
    if keyword_result["flags"] and not has_compliance_gap and compliance_verdict == "SAFE":
        # We just injected a compliance gap the LLM missed — the verdict can't stay "SAFE".
        compliance_verdict = "MEDIUM_RISK"

    return JobMatchResponse(
        compliance_verdict=compliance_verdict,
        overall_match_score=final_match_score,
        detected_gaps=detected_gaps,
        optimized_profile=optimized_profile
    )

if __name__ == "__main__":
    uvicorn.run("app.main:app", host = "127.0.0.1", port = 8000, reload = True)