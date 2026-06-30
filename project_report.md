# Scam-Det: Enterprise Fraud Defense Architecture Deep-Dive

## Executive Summary
Scam-Det represents a paradigm shift in automated fraud defense. Traditional B2B security honeypots rely on static rulesets, keyword matching, and hardcoded dialogue trees. Modern scammers, equipped with their own AI tools, easily identify and bypass these static traps. 

Scam-Det introduces the **Chameleon Brain**, a dynamic, multi-agent LLM architecture that acts as a highly convincing, vulnerable victim. Designed as a headless, stateful API, it is intended to sit behind communications gateways (SMS, WhatsApp, Email) to intercept, engage, and silently extract actionable threat intelligence from scammers at scale.

## Ingenious Architectural Highlights

### 1. The Multi-Agent Pipeline (The Chameleon Brain)
Relying on a single, massive LLM prompt often leads to catastrophic hallucinations, character breaking, or the AI revealing its robotic nature. Scam-Det mitigates this by splitting the cognitive load across four specialized virtual agents within the core logic layer:

1. **The Profiler:** Evaluates the initial inbound payload and dynamically constructs a hyper-specific victim persona (e.g., "Uncle Verma, 55, frustrated with tech" for tech support scams, or "Rohan, 20, broke student" for job scams).
2. **The Analyst (Grounding Layer):** Reviews the conversation history array and extracts *hard facts* (e.g., mentioned amounts, requested tasks, conversation phase). This completely eliminates the LLM's tendency to invent fake numbers or hallucinate past events, providing a grounded reality for the AI.
3. **The Director (Strategic Layer):** Consumes the Analyst's facts and the Profiler's persona to determine the *strategic next step* (e.g., "The scammer asked for a screenshot, use the 'I am at an office PC' excuse to stall").
4. **The Actor:** The final generation layer that strictly follows negative constraints (e.g., use bad grammar, never ask multiple questions simultaneously) and executes the Director's strategy in character.

### 2. State-Driven Hallucination Prevention
A critical challenge in generative AI security tooling is ensuring the agent doesn't accidentally help the adversary (e.g., acting like the customer support agent). Scam-Det solves this by explicitly tracking the "Money Flow" (Inbound vs. Outbound) and injecting rigid negative constraints.
- If the scammer is promising money (Job Scam), the AI aggressively demands its payout, forcing the scammer into a corner.
- If the scammer is demanding money (Tech Support), the AI utilizes stall tactics and fake compliance. 
The Actor is cryptographically barred from asking for multiple pieces of intelligence at once, ensuring the conversation flows naturally over dozens of messages.

### 3. Asynchronous Intelligence Webhooks
The system operates completely asynchronously. While the LLM pipeline generates conversational replies, a lightweight, parallel regex and NLP parser extracts critical threat intelligence:
- UPI IDs
- Phone Numbers
- Bank Account Strings
- Phishing URLs

This data is maintained in the API's session state. Once sufficient intelligence is extracted, or the conversation reaches a natural termination phase, the backend fires asynchronous POST requests to a configurable `CALLBACK_URL` webhook, delivering real-time threat intelligence directly to a company's SIEM or security operations dashboard.

## Technical Stack
- **Backend:** Python, FastAPI (for high-concurrency, asynchronous API handling).
- **AI Integration:** LangChain & LiteLLM (via OpenRouter). We enforce the use of high-tier frontier models (e.g., Claude 3.5 Sonnet, GPT-4o) as the system requires exceptional instruction-following and roleplay capabilities that smaller, open-weight models lack.
- **Deployment:** Zero-UI, pure REST API designed for headless dockerized deployment.

## Conclusion
Scam-Det successfully demonstrates how advanced prompt engineering, multi-agent workflows, and state-tracking can be combined to build an autonomous, highly convincing defensive security API. It transforms the concept of a honeypot from a passive trap into an active, intelligent adversary against digital fraud at enterprise scale.
