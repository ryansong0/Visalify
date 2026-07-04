from fastapi import APIRouter, HTTPException
from app.services.analyzer import agent_service
from pydantic import BaseModel
from typing import List, Dict
import json

router = APIRouter()

class ChatSessionPayload(BaseModel):
    history: List[Dict[str, str]]

@router.post("/chat")
async def process_agent_turn(payload: ChatSessionPayload):
    if not payload.history:
        raise HTTPException(status_code = 400, detail = "Conversation history cannot be empty.")
        
    raw_response_json = agent_service.execute_chat_turn(payload.history)
    
    try:
        return json.loads(raw_response_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code = 500, detail = "Internal Orchestrator failed to format structured JSON response.")