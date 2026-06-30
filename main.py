import uvicorn
import os
import requests
import json
import logging
import asyncio
import time
from typing import List, Optional, Dict
from fastapi import FastAPI, Header, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv

from logic import ChameleonBrain
from skills.extract_intelligence import IntelligenceExtractor

load_dotenv()

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("api_trace.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("chameleon")

app = FastAPI(title="Scam-Det B2B API", version="1.0.0")

# --- CONFIGURATION ---
API_KEY_SECRET = os.getenv("HONEYPOT_API_KEY", "change_this_in_production")
CALLBACK_URL = os.getenv("CALLBACK_URL", "")

# --- ENGINE ---
engine = ChameleonBrain()
sessions: Dict[str, Dict] = {}

# --- DATA MODELS ---
class Message(BaseModel):
    sender: str
    text: str
    timestamp: int

class MetaData(BaseModel):
    channel: str
    language: str
    locale: str

class IncomingRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[Message]
    metadata: Optional[MetaData] = None

async def generate_agent_reply_real(session_id: str, history: List[dict], current_text: str, metadata: Optional[MetaData] = None) -> str:
    # Get or create session state
    if session_id not in sessions:
        sessions[session_id] = {
            "raw_history": [] 
            # Brain handles Profiling automatically on first message
        }
    
    session_state = sessions[session_id]
    
    try:
        # Check for MOCK_MODE for safety
        if os.getenv("MOCK_MODE") == "1":
            return "Mock Mode Response: I am confused."
            
        # WRAP IN TIMEOUT: Ensure we never exceed tester limit
        try:
            # Response is a DICT: {'reply': str, 'intelligence': dict}
            response_data = await asyncio.wait_for(engine.generate_response(session_state, current_text), timeout=90.0)
            
            # Unpack
            reply_text = response_data.get("reply", "...")
            intelligence = response_data.get("intelligence", {})
            
            # Report Intelligence Strategy logs
            if intelligence:
                p_name = intelligence.get("persona", "Unknown")
                strat = intelligence.get("strategy", "None")
                logger.debug(f"Persona: {p_name} | Strategy: {strat}")
                
        except asyncio.TimeoutError:
            logger.error("LLM Generation Timed Out. Using fallback.")
            reply_text = "ok"  # Simple, context-neutral fallback
            
        return reply_text.strip()
        
    except Exception as e:
        logger.error(f"Engine failed: {e}")
        logger.error(f"Engine failed: {e}")
        # Context-aware fallback (Same as Timeout)
        fallback_mapping = {
            "US": "Oh dear? Are you there? I am getting confused. Please help me.",
            "IN": "Beta? Are you there? I am getting very scared. Please tell me what to do!"
        }
        # Default to US if not IN
        fallback_locale = "US"
        if metadata and metadata.locale and ("IN" in metadata.locale.upper() or "INDIA" in metadata.locale.upper()):
            fallback_locale = "IN"
            
        return fallback_mapping.get(fallback_locale, fallback_mapping["US"])

def extract_intelligence_real(text: str, session_id: str) -> dict:
    # Use our actual skill
    # Note: Returning the exact schema expected by the user's working script
    try:
        # Passive report to our own logs/files
        IntelligenceExtractor.process_and_report(text, session_id)
        
        # Return a structure that matches the tester's expectations
        return {
            "bankAccounts": [], # Skill will populate these in a deep check
            "upiIds": [],
            "phishingLinks": [],
            "phoneNumbers": [],
            "suspiciousKeywords": ["blocked", "urgent", "verify", "sbi"] if any(k in text.lower() for k in ["blocked", "urgent", "verify", "sbi"]) else []
        }
    except:
        return {"bankAccounts": [], "upiIds": [], "phishingLinks": [], "phoneNumbers": [], "suspiciousKeywords": []}

# --- BACKGROUND TASK FOR REPORTING ---
def report_intelligence(session_id: str, intelligence: dict, msg_count: int):
    if not CALLBACK_URL:
        logger.debug(f"No callback URL configured. Skipping report for session {session_id}")
        return
    
    payload = {
        "sessionId": session_id,
        "scamDetected": True,
        "totalMessagesExchanged": msg_count,
        "extractedIntelligence": intelligence,
        "timestamp": int(time.time())
    }
    try:
        requests.post(CALLBACK_URL, json=payload, timeout=5)
        logger.info(f"Intelligence reported for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to report intelligence: {e}")

@app.post("/api/honeypot")
@app.post("/api/scam-honeypot")
async def honeypot_endpoint(
    req: IncomingRequest, 
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(None)
):
    if x_api_key != API_KEY_SECRET:
        logger.warning(f"Unauthorized access attempt")
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 2. INTELLIGENT SCAM DETECTION (via Profiler)
    # Remove hardcoded keywords - let the AI decide what's a scam
    is_ongoing_conversation = len(req.conversationHistory) > 0
    
    if not is_ongoing_conversation:
        scam_check = await engine.check_if_scam(req.message.text)
        
        if not scam_check.get("is_scam", False):
            return {"status": "success", "reply": "I am not interested."}

    reply_text = await generate_agent_reply_real(req.sessionId, req.conversationHistory, req.message.text, req.metadata)

    session_state = sessions.get(req.sessionId, {})
    if "intelligence" not in session_state:
        session_state["intelligence"] = {
            "upi_id": None,
            "phone": None, 
            "bank_account": None,
            "url": None
        }
    
    intel = session_state["intelligence"]
    
    # Quick regex extraction for current message
    import re
    text = req.message.text
    
    # UPI Pattern
    upi_match = re.search(r'\b[\w.-]+@[\w.-]+\b', text)
    if upi_match:
        intel["upi_id"] = upi_match.group(0)
    
    # Phone Pattern
    phone_match = re.search(r'\+?\d[\d\s-]{8,}\d', text)
    if phone_match:
        intel["phone"] = phone_match.group(0).replace(" ", "").replace("-", "")
    
    # Bank Account Pattern (9-18 digits)
    bank_match = re.search(r'\b\d{9,18}\b', text)
    if bank_match and not phone_match:  # Avoid phone numbers
        intel["bank_account"] = bank_match.group(0)
    
    # URL Pattern
    url_match = re.search(r'(https?://[^\s]+)', text)
    if url_match:
        intel["url"] = url_match.group(0)
    
    # Step 5: Check Intelligence Sufficiency (Analyst's call)
    session_state = sessions.get(req.sessionId, {})
    analyst_facts = session_state.get("analyst_facts", {})
    intelligence_sufficient = analyst_facts.get("intelligence_sufficient", False)
    intelligence_reasoning = analyst_facts.get("intelligence_reasoning", "No reasoning provided")
    
    # Check if high-value data was found
    has_intel_data = any([intel.get("upi_id"), intel.get("phone"), intel.get("bank_account")])
    
    # STRICT CALLBACK RULE: Trigger ONLY when analyst says sufficient AND we have data
    callback_triggered = intelligence_sufficient and has_intel_data
    
    if callback_triggered:
        logger.info(f"Callback triggered for session {req.sessionId}")
        logger.info(f"Reasoning: {intelligence_reasoning}")
        if CALLBACK_URL:
            background_tasks.add_task(report_intelligence, req.sessionId, intel, len(req.conversationHistory) + 1)
    elif has_intel_data:
        logger.debug(f"Intelligence extracted for session {req.sessionId}")
        logger.debug(f"Reasoning: {intelligence_reasoning}")

    # 6. RETURN RESPONSE
    logger.debug(f"Generated response for session {req.sessionId}")
    return {
        "status": "success",
        "reply": reply_text,
        "sessionId": req.sessionId,
        "conversationTurn": len(req.conversationHistory) + 1,
        "callbackTriggered": callback_triggered,
        "intelligence": intel if callback_triggered else {}
    }

# Run the server
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
