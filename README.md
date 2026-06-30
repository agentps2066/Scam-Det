# Scam-Det: Autonomous Fraud Intelligence API 🛡️

Scam-Det is a highly scalable, stateful, LLM-powered API backend designed for enterprise fraud defense. It operates as an autonomous honeypot, designed to intercept inbound communications from scammers, dynamically engage them via intelligent multi-agent personas, and silently extract actionable threat intelligence (UPI IDs, bank accounts, phishing URLs, and phone numbers).

This repository provides the core headless API infrastructure intended for programmatic integration into your existing security operations or communication pipelines (e.g., Twilio, WhatsApp Business API, email gateways).

## Architectural Overview

The core of Scam-Det is the **Chameleon Brain**, a sophisticated multi-agent pipeline built on LangChain. It replaces static, rule-based auto-replies with dynamic, context-aware conversations.

1. **Incoming Message:** Your system routes a suspected scam message to the `/api/honeypot` endpoint.
2. **The Profiler:** If it's a new conversation, the AI automatically generates a victim persona (e.g., a panicked senior citizen for tech support scams, or a greedy student for job scams).
3. **The Analyst & Director:** Subsequent messages are evaluated by internal agents that extract facts and determine strategic engagement (e.g., stalling, fake compliance, extracting payment methods) without breaking character.
4. **Intelligence Webhook:** As actionable data is extracted, the backend fires asynchronous POST requests to your configured `CALLBACK_URL` webhook, delivering real-time threat intelligence.

## Setup & Deployment

### 1. Requirements
- Python 3.9+
- A high-tier LLM API Key (via [OpenRouter.ai](https://openrouter.ai/))

### 2. Installation
```bash
git clone https://github.com/yourusername/Scam-Det.git
cd Scam-Det
pip install -r requirements.txt # (fastapi uvicorn requests pydantic python-dotenv langchain-openai)
```

### 3. Environment Configuration
Create a `.env` file in the root directory:

```env
HONEYPOT_API_KEY=your_secure_api_key_here

OPENROUTER_API_KEY=your_openrouter_api_key

# ⚠️ CRITICAL: We strongly recommend flagship paid models for optimal performance.
# Free or quantized models often struggle with the complex negative constraints and 
# multi-agent roleplay required by the Chameleon Brain, leading to hallucinations.
LLM_MODEL=anthropic/claude-3.5-sonnet

# The webhook endpoint on your servers to receive extracted intelligence
CALLBACK_URL=https://api.yourcompany.com/webhooks/scam-intel
```

### 4. Running the Server
Start the FastAPI server:
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Documentation

### Endpoint: `/api/honeypot`
**Method:** `POST`

**Headers:**
- `Content-Type: application/json`
- `x-api-key: <your_HONEYPOT_API_KEY>`

**Request Payload Example:**
```json
{
  "sessionId": "unique-session-id-123",
  "message": {
    "sender": "scammer",
    "text": "Your account is blocked. Send $500 to verify@bank immediately to unlock it.",
    "timestamp": 1718000000
  },
  "conversationHistory": [],
  "metadata": {
    "channel": "whatsapp",
    "language": "en",
    "locale": "US"
  }
}
```

**Response Example:**
```json
{
  "status": "success",
  "reply": "Oh no! My account is blocked? What do I need to do? I am very confused.",
  "intelligence_extracted": {
    "bankAccounts": [],
    "upiIds": [],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": ["blocked", "verify"]
  }
}
```

### Intelligence Webhook Payload
When the system extracts critical intelligence or hits a dead end with the scammer, it will fire an asynchronous POST request to your `CALLBACK_URL`.

**Webhook Payload:**
```json
{
  "sessionId": "unique-session-id-123",
  "scamDetected": true,
  "totalMessagesExchanged": 4,
  "extractedIntelligence": {
    "bankAccounts": ["4567-XXXX-XXXX-1234"],
    "upiIds": ["scammer@paytm"],
    "phishingLinks": ["http://fake-bank-login.com"],
    "phoneNumbers": ["+1-555-0192"]
  },
  "timestamp": 1718000050
}
```

## License
MIT License
