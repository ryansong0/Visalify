import httpx
import json
import logging
from typing import Dict, Any
from app.config import settings
from app.utils.helpers import clamp_score
from app.schemas import ChatAnalysisResponse, RiskFlag
from app.services.vector_scan import vector_scanner

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger("VisalifyAgent")

class LlmAgentService:
    @staticmethod
    def _get_structured_schema() -> Dict[str, Any]:
        """Defines the strict JSON schema the LLM MUST return."""
        return {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["CRITICAL_HIGH_RISK", "MEDIUM_RISK", "LOW_RISK", "SAFE"]},
                "explanation": {"type": "string"},
                "optimized_text": {"type": "string", "description": "The rewritten, compliant version of the input data"}
            },
            "required": ["verdict", "explanation", "optimized_text"]
        }  

    @staticmethod
    def _get_matcher_schema() -> Dict[str, Any]:
        """Defines the strict JSON schema for the dual profile + job description optimization pipeline."""
        return {
            "type": "object",
            "properties": {
                "compliance_verdict": {"type": "string", "enum": ["CRITICAL_HIGH_RISK", "MEDIUM_RISK", "LOW_RISK", "SAFE"]},
                "overall_match_score": {"type": "integer", "minimum": 0, "maximum": 100},
                "detected_gaps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "enum": ["Regulatory Compliance Risk", "Technical Skill Gap"]},
                            "detected_risk": {"type": "string"},
                            "optimization_strategy": {"type": "string"}
                        },
                        "required": ["category", "detected_risk", "optimization_strategy"]
                    }
                },
                "optimized_profile": {"type": "string"}
            },
            "required": ["compliance_verdict", "overall_match_score", "detected_gaps", "optimized_profile"]
        } 

    @classmethod
    async def run_optimization_pipeline(cls, latest_input: str, flag_context: str) -> Dict[str, Any]:
        """Legacy standalone profile optimization pipeline (Keep this active for backward compatibility)."""
        system_prompt = f"You are Visalify AI. Analyze this profile against compliance flags:\n{flag_context}"
        payload = {
            "model": settings.LLM_MODEL,
            "prompt": f"{system_prompt}\n\nCandidate Profile Input: {latest_input}",
            "stream": False,
            "format": cls._get_structured_schema()
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{settings.OLLAMA_URL}/api/generate", json=payload, timeout=120.0)
                if response.status_code == 200:
                    return json.loads(response.json().get("response", "{}"))
            except Exception as e:
                logger.error(f"Legacy Pipeline Failure: {e}")
            return {"verdict": "SAFE", "explanation": "Fallback active.", "optimized_text": latest_input}
        
        
    @staticmethod
    def _get_detection_schema() -> Dict[str, Any]:
        """Schema for detection + scoring only — no rewrite responsibility."""
        return {
            "type": "object",
            "properties": {
                "compliance_verdict": {"type": "string", "enum": ["CRITICAL_HIGH_RISK", "MEDIUM_RISK", "LOW_RISK", "SAFE"]},
                "overall_match_score": {"type": "integer", "minimum": 0, "maximum": 100},
                "detected_gaps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "enum": ["Regulatory Compliance Risk", "Technical Skill Gap"]},
                            "detected_risk": {"type": "string"},
                            "optimization_strategy": {"type": "string"}
                        },
                        "required": ["category", "detected_risk", "optimization_strategy"]
                    }
                }
            },
            "required": ["compliance_verdict", "overall_match_score", "detected_gaps"]
        }

    @staticmethod
    def _get_rewrite_schema() -> Dict[str, Any]:
        """Schema for rewrite only — no scoring/detection responsibility."""
        return {
            "type": "object",
            "properties": {
                "optimized_profile": {"type": "string"}
            },
            "required": ["optimized_profile"]
        }

    @classmethod
    async def run_detection_pipeline(cls, candidate_profile: str, job_description: str, flag_context: str, computed_match_score: int = 50) -> Dict[str, Any]:
        """
        STAGE 1 ONLY: Detect skill gaps and compliance risks, and score the match.
        Does NOT rewrite the profile — that's a separate call.
        """
        logger.info("Executing Detection & Scoring pipeline...")

        system_prompt = f"""
        You are the detection engine of Visalify. Your ONLY job is to analyze — you do not rewrite anything.

        1. SKILL GAP ANALYTICS: Compare the Candidate Profile with the target Job Description. 
        Identify only skills/tools/technologies explicitly required by the Job Description that are 
        genuinely absent from the Candidate Profile — do not flag a skill as missing if the candidate's 
        resume already demonstrates it, even indirectly (e.g. if the job asks for "database optimization" 
        and the resume describes optimizing a database, that is a MATCH, not a gap).
        Only include a "Technical Skill Gap" entry if the computed technical similarity score is below 50 
        AND you can name a specific technology genuinely absent from the resume. Do not invent a gap just 
        to satisfy this requirement — if the skills genuinely align, leave 'detected_gaps' empty for this category.

        SCORING RULE: A preliminary technical similarity score of {computed_match_score} has already 
        been computed independently via embeddings. Use it as your baseline for 'overall_match_score' — 
        adjust by at most ±10 points. Never reduce this score because of compliance/visa-risk language.

        CRITICAL — NO FABRICATION: Only reference text that is verbatim present in the CANDIDATE PROFILE. 
    r paraphrase a sentence from the JOB DESCRIPTION as if it came from the candidate's resume.

        2. COMPLIANCE ENFORCEMENT: A separate detection system has already scanned the candidate profile 
        for supervisory/managerial language and found these specific matches:
        {flag_context if flag_context else "NONE — the pre-scan found no supervisory or managerial language in this profile."}

        FIELD FORMAT RULES (apply to BOTH Regulatory Compliance Risk and Technical Skill Gap entries):
- 'detected_risk' must always be a complete, natural sentence in plain English. NEVER use 
  all-caps labels, underscores, or enum-style tokens (e.g. never write "GO_AND_RUST skill gap" — 
  instead write "The job requires experience with Go and Rust, which aren't listed in your resume").
- 'optimization_strategy' must always be a complete, natural sentence giving concrete guidance, 
  never a short fragment or label.

        You must base 'detected_gaps' Regulatory Compliance Risk entries ONLY on the matches listed above. 
        If the pre-scan found NONE, you MUST NOT include a "Regulatory Compliance Risk" gap under any 
        circumstances — do not perform your own independent search for risk language, and do not invent, 
        infer, or extrapolate a risk from phrases that were not listed above. The pre-scan list is your 
        only source of truth for this category.

        NEVER suggest that a candidate add, highlight, or emphasize managerial/leadership language — 
   this tool exists exclusively to reduce visa risk by removing such language, never to add it. 
   If there is no compliance risk to report, do not manufacture one by suggesting the opposite.

        Respond strictly as valid JSON matching the schema. No markdown, no code fences.
        """

        url = f"{settings.OLLAMA_URL}/api/generate"
        payload = {
            "model": settings.LLM_MODEL,
            "prompt": f"{system_prompt}\n\n[CANDIDATE PROFILE]:\n{candidate_profile}\n\n[TARGET JOB DESCRIPTION]:\n{job_description}",
            "stream": False,
            "format": cls._get_detection_schema()
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=120.0)
                if response.status_code == 200:
                    raw_data = response.json().get("response", "{}")
                    logger.info("Detection pipeline succeeded.")
                    return json.loads(raw_data)
            except Exception as e:
                logger.error(f"Detection Pipeline Failure: {type(e).__name__}: {e!r}")

            return {
                "compliance_verdict": "SAFE",
                "overall_match_score": computed_match_score,
                "detected_gaps": [{"category": "Technical Skill Gap", "detected_risk": "Detection pipeline unavailable.", "optimization_strategy": "Verify Ollama connectivity."}]
            }

    @classmethod
    async def run_rewrite_pipeline(cls, candidate_profile: str, detected_gaps: list) -> str:
        """
        STAGE 2 ONLY: Rewrite the candidate profile to remove supervisory language.
        Only ever sees the resume — never the job description — to avoid cross-contamination.
        """
        logger.info("Executing Rewrite pipeline...")

        gaps_summary = "\n".join(
            f"- [{g.get('category', '')}] {g.get('detected_risk', '')}" for g in detected_gaps
        ) or "No specific gaps provided; use general judgment."

        system_prompt = f"""
        You are the rewrite engine of Visalify. Your ONLY input is the candidate's resume text below — 
        you have no knowledge of any job description, and must not reference or include one.

        Known issues to address in this specific text:
        {gaps_summary}

        TASK: Rewrite EVERY sentence in the resume that contains managerial or supervisory language. 
        Process the text sentence-by-sentence. For each sentence, check if it contains words like 
        "managed," "led," "directed," "overseeing," "oversaw," or similar supervisory framing — if so, 
        rewrite that sentence into hands-on technical framing. Do not stop after the first rewrite; 
        apply this to every applicable sentence in the full text.

        Example: "Managed a team of 6 engineers building microservices" becomes "Architected and 
        implemented microservices, collaborating with a 6-person engineering team on system design."

        Keep all technical skills, metrics, and factual content intact — only reframe the 
        supervisory language. Output must be plain text only: no HTML tags, no markdown, no code fences.
        The final text must contain ZERO instances of "managed," "led," "directed," "overseeing," or "oversaw."

        CRITICAL: Your output must be the FULL rewritten resume, matching the original in length and 
        completeness. Do not truncate, summarize, or drop any part of the original text (job history, 
        metrics, or the Skills line). Every sentence and every skill listed in the original must appear 
        in your output, rewritten only where supervisory language needs reframing.

        Respond strictly as valid JSON matching the schema.
        """

        url = f"{settings.OLLAMA_URL}/api/generate"
        payload = {
            "model": settings.LLM_MODEL,
            "prompt": f"{system_prompt}\n\n[RESUME TEXT TO REWRITE]:\n{candidate_profile}",
            "stream": False,
            "format": cls._get_rewrite_schema()
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=120.0)
                if response.status_code == 200:
                    raw_data = response.json().get("response", "{}")
                    parsed = json.loads(raw_data)
                    optimized_profile = parsed.get("optimized_profile", candidate_profile)

                    if len(optimized_profile.strip()) < len(candidate_profile.strip()) * 0.6:
                        logger.error("Rewrite output too short — falling back to original profile.")
                        return candidate_profile

                    logger.info("Rewrite pipeline succeeded.")
                    return optimized_profile
            except Exception as e:
                logger.error(f"Rewrite Pipeline Failure: {type(e).__name__}: {e!r}")

            return candidate_profile