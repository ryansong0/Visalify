from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import numpy as np
import requests
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import uvicorn
import traceback

app = FastAPI(title = "VisaGuard Compliance Engine (Vector Edition)", version = "2.0")

print("Loading semantic embedding model...")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

REGULATORY_KB = [
    {
        "category": "Management Consultant",
        "anchor_phrases": [
            "managing day to day operations and staff",
            "execution of corporate business strategy",
            "operating in a daily managerial or executive capacity",
            "directing product lines and project management timelines"
        ],
        "reason": "Explicitly flagged under 8 CFR 214.6. Management consultants must strictly operate in an advisory capacity, not operational management or day-to-day execution.",
        "alternative": "Reframe responsibilities around 'strategic evaluation', 'process auditing', or 'operational assessment'.",
        "base_weight": 60
    },
    {
        "category": "Non-Statutory Product Management",
        "anchor_phrases": [
            "owning product roadmap and business market fit",
            "cross functional team leadership and revenue metrics",
            "managing feature prioritization and marketing alignment",
            "product manager responsible for lifecycle execution"
        ],
        "reason": "Product Management is not a recognized statutory profession under the TN classification system. High risk of immediate denial if not aligned under a valid engineering or scientific category.",
        "alternative": "Re-evaluate if duties align with 'Computer Systems Analyst' or 'Engineer', focusing entirely on architecture rather than business metrics.",
        "base_weight": 85
    }
]

for rule in REGULATORY_KB:
    rule["embeddings"] = model.encode(rule["anchor_phrases"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatHistoryRequest(BaseModel):
    history: List[ChatMessage]

class RiskFlag(BaseModel):
    matched_text: str
    reason: str
    suggested_alternative: str

class ChatAnalysisResponse(BaseModel):
    agent_message: str
    risk_score: int
    overall_risk_level: str
    requires_more_info: bool
    flags: List[RiskFlag]


def vector_compliance_scan(latest_input: str, threshold: float = 0.42) -> tuple:
    flags = []
    max_observed_score = 0
    
    if not latest_input.strip():
        return 0, "Safe", True, []
    
    user_embedding = model.encode([latest_input])

    for rule in REGULATORY_KB:
        similarities = cosine_similarity(user_embedding, rule["embeddings"])[0]
        max_sim_idx = np.argmax(similarities)
        highest_similarity = similarities[max_sim_idx]

        if highest_similarity > threshold:
            scaled_penalty = int(rule["base_weight"] * (highest_similarity ** 2))
            max_observed_score = max(max_observed_score, scaled_penalty)

            flags.append(RiskFlag(
                matched_text = rule["anchor_phrases"][max_sim_idx],
                reason = f"Matched regulatory restriction context via category '{rule['category']}' (Semantic Confidence: {highest_similarity:.2f}). {rule['reason']}",
                suggested_alternative = rule["alternative"]
            ))

    risk_score = min(100, max_observed_score)

    
    if risk_score >= 75:
        level = "Critical"
    elif risk_score >= 45:
        level = "High"
    elif risk_score >= 20:
        level = "Medium"
    else:
        level = "Safe"
        
    requires_more = len(latest_input.split()) < 15 or risk_score == 0
    
    return risk_score, level, requires_more, flags

@app.post("/chat", response_model = ChatAnalysisResponse)
async def analyze_compliance_dialogue(payload: ChatHistoryRequest):
    user_messages = [m.content for m in payload.history if m.role == "user"]
    if not user_messages:
        return ChatAnalysisResponse(
            agent_message = "I'm ready when you are. Please paste a job description or list your core responsibilities.",
            risk_score = 0,
            overall_risk_level = "Safe",
            requires_more_info = True,
            flags = []
        )
        
    latest_user_input = user_messages[-1]

    risk_score, risk_level, requires_more, flags = vector_compliance_scan(
        latest_user_input
    )

    flag_context = "\n".join([f"- Context Flag: '{f.matched_text}'\n  Reason: {f.reason}" for f in flags])

    system_prompt = f"""
    You are VisaGuard AI, an expert immigration compliance assistant specializing in 8 CFR 214.6 regulations.
    Current Telemetry: Risk Score {risk_score}/100, Tier: {risk_level}.
    {flag_context}
    
    INSTRUCTIONS:
    Be concise (under 4 sentences). Identify why the phrasing sounds non-compliant. Provide a 1-sentence compliant rewrite alternative.
    """

    try:
        ollama_url = "http://127.0.0.1:11434/api/generate"
        ollama_payload = {
            "model": "llama3.2:latest",
            "prompt": f"{system_prompt}\n\nUser Input to Analyze: {latest_user_input}",
            "stream": False
        }
        
        response = requests.post(ollama_url, json = ollama_payload, timeout = 60)
        if response.status_code == 200:
            reply = response.json().get("response", "Analysis processed.")
        else:
            reply = "Local AI loop tracking anomaly. Please verify Ollama system runtime parameters."
    except Exception as e:
        print("\n" + "="*50)
        print("🚨 CRITICAL BACKEND ERROR CAUGHT:")
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Message: {e}")
        print("\nFull Traceback:")
        traceback.print_exc()
        print("="*50 + "\n")
        raise HTTPException(status_code = 500, detail = "Internal processing error")
    
    return ChatAnalysisResponse(
        agent_message = reply,
        risk_score = risk_score,
        overall_risk_level = risk_level,
        requires_more_info = requires_more,
        flags = flags
    )

if __name__ == "__main__":
    uvicorn.run("main.py:app", host = "127.0.0.1", port = 8000, reload = True)