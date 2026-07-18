import httpx
import json
import re
import logging
from typing import Dict, Any
from app.config import settings
from app.utils.helpers import clamp_score
from app.schemas import ChatAnalysisResponse, RiskFlag
from app.services.vector_scan import vector_scanner

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger("VisalifyAgent")

class LlmAgentService:
    @classmethod
    async def _call_groq(cls, client: httpx.AsyncClient, system_prompt: str, user_content: str, timeout: float = 60.0) -> Dict[str, Any]:
        """POST a chat-completion request to Groq's OpenAI-compatible API and return the parsed JSON body."""
        response = await client.post(
            f"{settings.GROQ_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            json={
                "model": settings.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        return json.loads(raw)

    @classmethod
    async def run_optimization_pipeline(cls, latest_input: str, flag_context: str) -> Dict[str, Any]:
        """Legacy standalone profile optimization pipeline (Keep this active for backward compatibility)."""
        system_prompt = f"""You are Visalify AI. Analyze this profile against compliance flags:
        {flag_context}

        Respond ONLY with a JSON object of this exact shape, no extra keys, no markdown:
        {{"verdict": "CRITICAL_HIGH_RISK" | "MEDIUM_RISK" | "LOW_RISK" | "SAFE", "explanation": "<string>", "optimized_text": "<the rewritten, compliant version of the input>"}}
        """
        async with httpx.AsyncClient() as client:
            try:
                return await cls._call_groq(client, system_prompt, f"Candidate Profile Input: {latest_input}", timeout=60.0)
            except Exception as e:
                logger.error(f"Legacy Pipeline Failure: {e}")
            return {"verdict": "SAFE", "explanation": "Fallback active.", "optimized_text": latest_input}

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
        Never paraphrase a sentence from the JOB DESCRIPTION as if it came from the candidate's resume.

        2. COMPLIANCE ENFORCEMENT: A separate detection system has already scanned the candidate profile
        for supervisory/managerial language and found these specific matches:
        {flag_context if flag_context else "NONE — the pre-scan found no supervisory or managerial language in this profile."}

        FIELD FORMAT RULES (apply to BOTH Regulatory Compliance Risk and Technical Skill Gap entries):
        - 'detected_risk' must always be a complete, non-empty, natural sentence in plain English. NEVER use
          all-caps labels, underscores, or enum-style tokens (e.g. never write "GO_AND_RUST skill gap" —
          instead write "The job requires experience with Go and Rust, which aren't listed in your resume").
        - 'optimization_strategy' must always be a complete, non-empty, natural sentence giving concrete guidance,
          never a short fragment, a label, or an empty string.
        - Never include a 'detected_gaps' entry unless both fields above are filled in with real sentences.

        You must base 'detected_gaps' Regulatory Compliance Risk entries ONLY on the matches listed above.
        If the pre-scan found NONE, you MUST NOT include a "Regulatory Compliance Risk" gap under any
        circumstances — do not perform your own independent search for risk language, and do not invent,
        infer, or extrapolate a risk from phrases that were not listed above. The pre-scan list is your
        only source of truth for this category.

        NEVER suggest that a candidate add, highlight, or emphasize managerial/leadership language —
        this tool exists exclusively to reduce visa risk by removing such language, never to add it.
        If there is no compliance risk to report, do not manufacture one by suggesting the opposite.

        Respond ONLY with a JSON object of this exact shape, no extra keys, no markdown, no code fences:
        {{"compliance_verdict": "CRITICAL_HIGH_RISK" | "MEDIUM_RISK" | "LOW_RISK" | "SAFE",
          "overall_match_score": <integer 0-100>,
          "detected_gaps": [{{"category": "Regulatory Compliance Risk" | "Technical Skill Gap", "detected_risk": "<string>", "optimization_strategy": "<string>"}}]}}
        """

        async with httpx.AsyncClient() as client:
            try:
                result = await cls._call_groq(
                    client, system_prompt,
                    f"[CANDIDATE PROFILE]:\n{candidate_profile}\n\n[TARGET JOB DESCRIPTION]:\n{job_description}",
                    timeout=60.0,
                )
                logger.info("Detection pipeline succeeded.")
                return result
            except Exception as e:
                logger.error(f"Detection Pipeline Failure: {type(e).__name__}: {e!r}")

            return {
                "compliance_verdict": "SAFE",
                "overall_match_score": computed_match_score,
                "detected_gaps": [{"category": "Technical Skill Gap", "detected_risk": "Detection pipeline unavailable.", "optimization_strategy": "Verify Groq API connectivity and API key."}]
            }

    _BANNED_TERM_REPLACEMENTS = {
        "managed": "coordinated",
        "led": "guided",
        "directed": "facilitated",
        "overseeing": "monitoring",
        "oversaw": "monitored",
    }

    @classmethod
    def _scrub_banned_terms(cls, text: str) -> str:
        """Deterministic last-resort safety net: swap any surviving banned
        supervisory verbs for a neutral synonym, preserving capitalization.
        Guarantees zero leakage even if the LLM fails the rewrite twice."""
        pattern = re.compile(r'\b(managed|led|directed|overseeing|oversaw)\b', re.IGNORECASE)

        def _replace(match: re.Match) -> str:
            word = match.group(0)
            replacement = cls._BANNED_TERM_REPLACEMENTS[word.lower()]
            return replacement.capitalize() if word[0].isupper() else replacement

        return pattern.sub(_replace, text)

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
        Preserve the ORIGINAL structure exactly: the same sentences in the same order, as flowing prose.
        Do not reformat the resume into a different structure — no JSON, no labeled fields like "title:"
        or "experience:", no bullet lists unless the original already used them. The output should read
        like the same resume, not a re-templated version of it.
        The final text must contain ZERO instances of "managed," "led," "directed," "overseeing," or "oversaw."

        CRITICAL: Your output must be the FULL rewritten resume, matching the original in length and
        completeness. Do not truncate, summarize, or drop any part of the original text (job history,
        metrics, or the Skills line). Every sentence and every skill listed in the original must appear
        in your output, rewritten only where supervisory language needs reframing.

        Respond ONLY with a JSON object of this exact shape, no extra keys, no markdown:
        {{"optimized_profile": "<the full rewritten resume as a single plain-text string>"}}
        """
        BANNED_TERMS_PATTERN = re.compile(r'\b(managed|led|directed|overseeing|oversaw)\b', re.IGNORECASE)
        user_content = f"[RESUME TEXT TO REWRITE]:\n{candidate_profile}"

        async with httpx.AsyncClient() as client:
            try:
                parsed = await cls._call_groq(client, system_prompt, user_content, timeout=60.0)
                optimized_profile = parsed.get("optimized_profile", candidate_profile)

                if len(optimized_profile.strip()) < len(candidate_profile.strip()) * 0.6:
                    logger.error("Rewrite output too short — falling back to original profile.")
                    return cls._scrub_banned_terms(candidate_profile)

                leaked = BANNED_TERMS_PATTERN.findall(optimized_profile)
                if leaked:
                    logger.warning(f"Rewrite leaked banned terms: {leaked} — retrying once.")
                    retry_prompt = (
                        f"{system_prompt}\n\nIMPORTANT: Your previous rewrite still contained "
                        f"these banned words: {', '.join(set(leaked))}. Remove them completely this time."
                    )
                    try:
                        retry_parsed = await cls._call_groq(client, retry_prompt, user_content, timeout=60.0)
                        retry_profile = retry_parsed.get("optimized_profile", optimized_profile)
                    except Exception as e:
                        logger.error(f"Retry request failed: {type(e).__name__}: {e!r} — applying deterministic scrub to first-draft rewrite.")
                        return cls._scrub_banned_terms(optimized_profile)

                    if not BANNED_TERMS_PATTERN.findall(retry_profile) and \
                       len(retry_profile.strip()) >= len(candidate_profile.strip()) * 0.6:
                        logger.info("Retry succeeded — banned terms removed.")
                        return retry_profile
                    logger.error(
                        "Retry still leaked banned terms — applying deterministic scrub as a last resort."
                    )
                    best_profile = retry_profile if len(retry_profile.strip()) >= len(candidate_profile.strip()) * 0.6 else optimized_profile
                    return cls._scrub_banned_terms(best_profile)

                logger.info("Rewrite pipeline succeeded.")
                return optimized_profile
            except Exception as e:
                logger.error(f"Rewrite Pipeline Failure: {type(e).__name__}: {e!r}")

            return cls._scrub_banned_terms(candidate_profile)
