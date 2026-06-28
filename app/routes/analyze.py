from fastapi import APIRouter

router = APIRouter()

@router.post("/analyze")
def analyze():
    return {
        "risk_level": "Medium",
        "summary": "This is a dummy response"
    }