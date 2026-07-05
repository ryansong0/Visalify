from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import uvicorn

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


def vector_compliance_scan(latest_input: str, SIMID_THRESHOLD: float = 0.42) -> tuple:

    
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
    if not payload.history:
        raise HTTPException(status_code = 400, detail = "Dialogue history cannot be empty.")
        
    # 1. Extract user state
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

    knowledge_base = {
        "management consultant": {
            "reason": "Explicitly flagged under 8 CFR 214.6. Management consultants must strictly operate in an advisory capacity, not operational management or day-to-day execution.",
            "alternative": "Reframe responsibilities around 'strategic evaluation', 'process auditing', or 'operational assessment'.",
            "weight": 50
        },
        "software engineer": {
            "reason": "While highly technical, using generalized software engineering titles under the 'Engineer' category requires strict alignment with an engineering degree. Borderline or non-traditional degrees invite heavy RFE scrutiny.",
            "alternative": "Specify the scientific or mathematical foundations of your systems engineering work.",
            "weight": 25
        },
        "product manager": {
            "reason": "Product Management is not a recognized statutory profession under the TN classification system. High risk of immediate denial if not aligned under a valid engineering or scientific category.",
            "alternative": "Re-evaluate if duties align with 'Computer Systems Analyst' or 'Engineer', focusing entirely on architecture rather than business metrics.",
            "weight": 80
        }
    }

    risk_score, risk_level, requires_more, flags = compute_compliance_telemetry(
        latest_user_input, knowledge_base
    )

    if risk_level in ["Critical", "High"]:
        reply = f"Analysis complete. I've flagged severe compliance conflicts with 8 CFR regulations. Specifically, the vocabulary matches patterns related to non-qualifying or heavily scrutinized roles like {', '.join([f.matched_text for f in flags])}. Look at the sidebar metrics for specific structural rewrites."
    elif requires_more:
        reply = "I've processed that phrase, but I need more details regarding your day-to-day responsibilities, reporting structure, and minimum degree requirements to generate an accurate risk matrix."
    else:
        reply = "The provided description shows high structural compliance alignment with standard TN occupational criteria. Keep regular monitoring active."

    return ChatAnalysisResponse(
        agent_message = reply,
        risk_score = risk_score,
        overall_risk_level = risk_level,
        requires_more_info = requires_more,
        flags = flags
    )

if __name__ == "__main__":
    uvicorn.run("main.py:app", host = "127.0.0.1", port = 8000, reload = True)