import json
import os
import re
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

class ChameleonBrain:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model=os.getenv("LLM_MODEL", "arcee-ai/trinity-large-preview:free"),
            default_headers={
                "HTTP-Referer": os.getenv("HTTP_REFERER", "https://localhost"), 
                "X-Title": os.getenv("APP_NAME", "ScamHoneypot")
            }
        )

    async def _invoke_llm(self, prompt: str, fallback: str = "ok") -> str:
        """Invoke LLM with timeout and error handling."""
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            raw_content = response.content
            
            content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
            
            if not content:
                return fallback
                
            return content
        except Exception as e:
            os.environ.get("DEBUG") and print(f"[LLM Error] {e}")
            return fallback

    def _get_style_constraints(self, metadata: Any) -> str:
        """Helper to generate style constraints based on metadata."""
        channel = "whatsapp"
        locale = "US"
        
        if metadata:
            if hasattr(metadata, 'channel'):
                channel = metadata.channel.lower()
            elif isinstance(metadata, dict):
                channel = metadata.get('channel', 'whatsapp').lower()
                
            if hasattr(metadata, 'locale'):
                locale = metadata.locale
            elif isinstance(metadata, dict):
                locale = metadata.get('locale', 'US')

        constraints = []
        
        if channel in ["whatsapp", "sms"]:
            constraints.append("MEDIUM: WhatsApp/SMS")
            constraints.append("- TYPING: Use lowercase mostly. Use short forms ('u', 'r', 'k').")
            constraints.append("- FORBIDDEN: Do NOT use perfect caps or ellipses ('...').")
            constraints.append("- CRITICAL: NEVER say 'I can't hear you'. We are text-only.")
        elif channel == "email":
            constraints.append("MEDIUM: Email")
            constraints.append("- FORMAT: MUST use a Subject line if first reply.")
            constraints.append("- SALUTATION: MUST start with 'Dear Sir/Madam,' or 'To Apple Support,'.")
            constraints.append("- BODY: Use proper grammar, full sentences, and official tone.")
            constraints.append("- SIGNATURE: MUST end with 'Regards, [Name]'.")
            
        if "IN" in locale.upper() or "INDIA" in locale.upper():
            constraints.append("REGION: India")
            constraints.append("- DIALECT: Use 'do one thing', 'revert back', 'network is gone'.")
            constraints.append("- TYPOS: 'wht' instead of 'what', 'fne' instead of 'fine'.")
        else:
            constraints.append("REGION: USA")
            constraints.append("- DIALECT: American English. Use 'Sir', 'Representative'.")
            
        return "\n".join(constraints)

    async def check_if_scam(self, message: str) -> Dict:
        """Determine if message is a scam attempt."""
        prompt = f"""
        TASK: Analyze if this message appears to be a scam.
        
        MESSAGE: "{message}"
        
        SCAM TYPES:
        - Job Scam (fake jobs, work-from-home)
        - Tech Support (Microsoft, virus)
        - Bank/KYC (account blocked)
        - Tax Fraud (IRS, warrant)
        - Romance/Sextortion
        - Package Delivery
        
        OUTPUT JSON ONLY:
        {{
            "is_scam": true or false,
            "scam_type": "Job|Tech|Bank|Tax|Romance|Package|Other" or "None"
        }}
        
        RULES:
        - If clearly a scam, return true.
        - If normal greeting, return false.
        - If unsure but suspicious, return true.
        """
        
        response = await self._invoke_llm(prompt)
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                return result
        except Exception as e:
            pass
        
        return {"is_scam": True, "scam_type": "Unknown"}

    async def profiler_step(self, first_message: str, metadata: Any) -> Dict:
        """
        Create victim persona based on scam type and context.
        Determines whether this is INBOUND (promised payment) or OUTBOUND (demanded payment).
        """
        channel = "whatsapp"
        locale = "US"
        if metadata:
            if hasattr(metadata, 'channel'):
                channel = metadata.channel.lower()
            if hasattr(metadata, 'locale'):
                locale = metadata.locale
        
        prompt = f"""
        TASK: Analyze scam message and create victim persona.
        
        SCAM MESSAGE: "{first_message}"
        CHANNEL: {channel}
        LOCALE: {locale}
        
        CRITICAL LOGIC (MONEY FLOW):
        - Job Scam/Lottery: INBOUND FLOW (Scammer promises to pay victim)
          → Create "Rohan/Rahul" (20yo broke student, greedy, uses slang)
          → money_flow: "INBOUND"
          
        - Tech Support/Virus: OUTBOUND FLOW (Scammer demands victim pays)
          → Create "Uncle Verma" (55yo frustrated with tech, formal, incompetent)
          → money_flow: "OUTBOUND"
          
        - Bank/KYC/Police: OUTBOUND FLOW
          → Create "Mrs. Sharma" (60yo panicked, anxious, rushes)
          → money_flow: "OUTBOUND"
        
        OUTPUT JSON ONLY:
        {{
            "name": "Rohan|Uncle Verma|Mrs. Sharma",
            "age": 20-60,
            "vibe": "Greedy|Frustrated|Panicked",
            "scam_type": "Job|Tech|Bank",
            "money_flow": "INBOUND|OUTBOUND",
            "writing_style": "lowercase_slang|formal|short_sentences"
        }}
        """
        
        response = await self._invoke_llm(prompt)
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                profile = json.loads(match.group(0))
                return profile
        except Exception as e:
            pass
        
        return {
            "name": "User", 
            "age": 50, 
            "vibe": "Confused", 
            "scam_type": "Unknown",
            "money_flow": "OUTBOUND",
            "writing_style": "Normal"
        }

    async def analyst_step(self, history: list, metadata: Any = None) -> Dict:
        """
        Extract conversation facts and state.
        Prevents hallucination by grounding decisions in concrete facts from chat history.
        """
        chat_log = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('text', '')}" for msg in history[-10:]])
        
        locale = "US"
        if metadata:
            if hasattr(metadata, 'locale'):
                locale = metadata.locale
            elif isinstance(metadata, dict):
                locale = metadata.get('locale', 'US')
        
        prompt = f"""
        ACT AS: Conversation Analyst (Fact Extractor + State Tracker).
        TASK: Analyze the chat history and extract HARD FACTS + CONVERSATION PHASE. Do NOT invent or assume.
        
        CHAT HISTORY:
        {chat_log}
        
        LOCALE: {locale}
        
        EXTRACT THE FOLLOWING (Return exact JSON):
        {{
            "mentioned_amount": "EXACT number the scammer mentioned (e.g., '500', '5000') OR 'None' if not mentioned",
            "mentioned_currency": "INR|USD|Rupees|Dollars OR 'None' if not mentioned",
            "task_description": "EXACT task scammer asked victim to do (e.g., 'like video', 'download teamviewer') OR 'None'",
            "task_status": "Asked|InProgress|Completed|None",
            "scammer_requested_screenshot": true or false,
            "scammer_provided_upi": "UPI ID if given OR 'None'",
            "scammer_offered_payment": true or false,
            "conversation_phase": "INTRO|TASK_GIVEN|PAYMENT_DEMAND|WAITING|UNKNOWN",
            "conversation_phase": "INTRO|TASK_GIVEN|PAYMENT_DEMAND|WAITING|UNKNOWN",
            "intelligence_sufficient": true or false,
            "intelligence_reasoning": "Briefly explain why intel is sufficient or not"
        }}
        
        CONVERSATION PHASE RULES (CRITICAL):
        - INTRO: Pitching or greeting. MUST be used for first 1-2 messages.
        - TASK_GIVEN: Specific instructions.
        - PAYMENT_DEMAND: Fee/Deposit request.
        - WAITING: Proof request.
        
        INTELLIGENCE SUFFICIENCY RULES (CRITICAL):
        Set "intelligence_sufficient" to TRUE ONLY if:
        1. We have a payment method (UPI/Phone/Bank).
        2. AND the scammer is ANGRY, FRUSTRATED, or GIVING UP.
        3. AND you have already asked for their company, website, AND phone number.
        
        DEAD END SIGNALS (REQUIRED FOR TRUE):
        - Scammer says "PAY NOW OR I BLOCK" or "FINAL WARNING".
        - Scammer uses excessive ALL CAPS for entire sentences.
        - Scammer stops answering questions and only repeats "Pay fee".
        
        IF SCAMMER IS STILL POLITE AND ANSWERING QUESTIONS, IT IS NOT A DEAD END. SET TO FALSE.
        """
        
        response = await self._invoke_llm(prompt)
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                facts = json.loads(match.group(0))
                return facts
        except Exception as e:
            pass
        
        return {
            "mentioned_amount": "None",
            "mentioned_currency": "None",
            "task_description": "None",
            "task_status": "None",
            "scammer_requested_screenshot": False,
            "scammer_provided_upi": "None",
            "scammer_offered_payment": False,
            "conversation_phase": "INTRO",
            "intelligence_sufficient": False,
            "intelligence_reasoning": "Fallback"
        }

    async def director_step(self, history: list, persona: Dict, analyst_facts: Dict, user_message: str, metadata: Any = None) -> str:
        """
        Determine next action strategy based on persona, facts, and conversation phase.
        Uses only concrete facts from analyst to prevent hallucination.
        """
        chat_log = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('text', '')}" for msg in history[-10:]])
        money_flow = persona.get("money_flow", "OUTBOUND")
        scam_type = persona.get("scam_type", "Unknown")
        
        # Get locale for currency enforcement
        locale = "US"
        if metadata:
            if hasattr(metadata, 'locale'):
                locale = metadata.locale
            elif isinstance(metadata, dict):
                locale = metadata.get('locale', 'US')
        
        # Determine correct currency symbol
        currency_symbol = "₹" if "IN" in locale.upper() else "$"
        currency_word = "Rupees" if "IN" in locale.upper() else "Dollars"
        
        if money_flow == "INBOUND":
            phase = analyst_facts.get('conversation_phase', 'INTRO')
            
            strategy = f"""
            INBOUND STRATEGY (Job/Lottery Scam):
            The scammer PROMISES to pay you. Your role: DEMAND the payout.
            
            ANALYST FACTS (GROUND TRUTH):
            - Mentioned Amount: {analyst_facts.get('mentioned_amount', 'None')}
            - Currency: {analyst_facts.get('mentioned_currency', 'None')}
            - Task: {analyst_facts.get('task_description', 'None')}
            - Task Status: {analyst_facts.get('task_status', 'None')}
            - CONVERSATION PHASE: {phase}
            
            LOCALE ENFORCEMENT:
            - You are in {locale}
            - Use ONLY: {currency_symbol} or "{currency_word}"
            - FORBIDDEN: Do NOT use "$" if locale is IN. Do NOT use "₹" if locale is US.
            
            🛑 HALLUCINATION PREVENTION RULES:
            - If mentioned_amount is "None", DO NOT invent a number. Ask: "How much will you pay?"
            - If mentioned_amount exists (e.g., "500"), use EXACTLY that number.
            - DO NOT change currency (if they said "$90", flag it but don't convert).
            
            🎯 PHASE-BASED STRATEGY (CRITICAL):
            
            IF Phase == 'INTRO':
              Role: Curious/Broke Student
              Action: Express interest but ASK DETAILS. DO NOT claim task completion.
              Example: "yeah i need money fast. what do i have to do? is it easy?"
              ASK FOR INTEL: "whats your company name?" or "do u have a website?"
              FORBIDDEN: Do NOT say "I liked the video" or claim ANY task completion.
            
            IF Phase == 'TASK_GIVEN':
              Role: Fast Worker
              Action: Claim you JUST finished the task AND give your UPI ID immediately.
              Example: "done i liked it. send my {analyst_facts.get('mentioned_amount', '500')} to rohan@paytm"
              CRITICAL: You must PROVIDE fake UPI (rohan@paytm, rahul123@phonepe) to RECEIVE payment.
              If no amount mentioned: "done. send payment to rohan@paytm"
            
            IF Phase == 'WAITING' (Screenshot Request):
              Role: Desktop Worker
              Action: Use "Office Desktop" excuse (NOT "stealth mode").
              Example: "im doing this on office computer sir. boss is sitting behind me i cant take photo with phone. just check the username rohan.kumar in your analytics"
              Alternative: "im on college lab pc cant lift my phone to take screenshot. check likes count it increased. my username is priya_sharma"
              ASK FOR INTEL: "btw whats your phone number in case i have issues later?"
              FORBIDDEN: Do NOT say "stealth mode", "camera broken", or "security policy".
              FORBIDDEN: Do NOT use generic usernames like "rohan123" or "user123". Use realistic ones: "rohan.kumar", "priya_sharma", "amit_verma"
            
            IF Phase == 'PAYMENT_DEMAND':
              Role: Negotiator
              Action: Refuse to pay registration fee. Demand your earnings first. Extract scammer details.
              Example: "no sir i already did the work. send my {analyst_facts.get('mentioned_amount', '500')} first to rohan@paytm then ill pay joining fee"
              ASK FOR INTEL: "whats your company registration number?" or "send me your website link so i can verify"
            """
        else:
            strategy = f"""
            🎯 INTELLIGENCE EXTRACTION PRIORITY (CRITICAL):
            Goal: Extract as much info as possible BEFORE scammer gives up.
            
            Ask for ONE of the following at a time (NEVER ASK FOR ALL AT ONCE):
            1. Phone number: "can u call me to walk me through this?"
            2. Website/URL: "is there an official website i can check?"
            3. Company name: "what company are u from again?"
            4. Reference number: "do u have a case number or ticket id?"
            5. Multiple payment methods: "do u take credit card? or only venmo?"
            
            Phase A (Try Technical): ONLY if scammer asks to download/click/install
              - "Download link is not opening"
              - "TeamViewer says connection refused"
              - ASK: "can u send me your phone number in case this fails?"
              FORBIDDEN: Do NOT offer to pay unless scammer explicitly asks for money.
            
            Phase B (Payment Offer): ONLY if scammer mentions payment/fee/fine/penalty
              - IF amount known: "ok i can pay {analyst_facts.get('mentioned_amount')}. but can u give me your phone number first? i wanna verify this is legit"
              - IF amount None: "how much do i need to pay? also whats your callback number?"
              - ASK: "do u have a website i can check?" or "whats your company name?"
            
            Phase C (Screenshot Trap - "SECURITY POLICY"):
              If screenshot requested:
              - "App showed 'Security Policy restricts screenshots'"
              - ASK: "can u call me instead? whats your number?"
            
            Phase D (Stall): ONLY after extracting phone/URL/company details
              - "Blue circle spinning..."
              - "Update Required popup"
              - "Payment pending..."
            """
        
        # Check if we have enough intelligence to end conversation
        intelligence_sufficient = analyst_facts.get('intelligence_sufficient', False)
        
        if intelligence_sufficient:
            # END CONVERSATION STRATEGY
            return """
            INTELLIGENCE EXTRACTION COMPLETE. End the conversation politely.
            Examples:
            - "ok sir i will try again later. thank you"
            - "sorry sir my phone is hanging. will call back"
            - "network issue sir. will message you tomorrow"
            DO NOT continue engaging. This is the LAST message.
            """
        
        prompt = f"""
        ACT AS: Strategic Director of Honeypot.
        CONTEXT: Victim is {persona['name']} ({persona['vibe']}).
        SCAM TYPE: {scam_type}
        MONEY FLOW: {money_flow}
        
        {strategy}
        
        CURRENT CHAT:
        {chat_log}
        
        LATEST SCAMMER MSG: "{user_message}"
        
        OUTPUT ONLY THE STAGE DIRECTION (Internal Monologue).
        Example: "Scammer asked for screenshot. Strategy: Use Stealth Mode excuse."
        """
        
        return await self._invoke_llm(prompt)

    async def actor_step(self, session_state: Dict, user_message: str, stage_direction: str, metadata: Any) -> str:
        """
        Generate dialogue based on persona, style constraints, and strategy direction.
        """
        profile = session_state.get("persona_profile", {
            "name": "User", 
            "age": 50, 
            "vibe": "Confused", 
            "writing_style": "Normal"
        })
        
        style_rules = self._get_style_constraints(metadata)
        
        prompt = f"""
        ROLE: You are {profile['name']}, {profile['age']}yo.
        VIBE: {profile['vibe']}.
        
        STAGE DIRECTION (FROM DIRECTOR):
        "{stage_direction}"
        
        CONTEXTUAL STYLE RULES:
        {style_rules}
        
        EXAMPLES OF FORMATTING (FOLLOW STRICTLY):
        
        If MEDIUM is Email:
        Subject: Re: [Original Subject]
        Dear [Name/Support],
        
        [Properly formatted paragraph with full sentences.]
        
        Sincerely,
        {profile['name']}
        
        If MEDIUM is WhatsApp:
        hey r u there? i tried opening the link but it didnt work. what do i do now?
        
        🛑 NEGATIVE CONSTRAINTS (CRITICAL):
        - YOU ARE THE VICTIM/CUSTOMER. 
        - NEVER act like the Bank, Customer Support, Representative, or the Scammer.
        - NEVER ask the scammer for their verification code. You are the one being scammed!
        - NEVER ask more than ONE question in a single message.
        - NEVER list out all the things you need. Ask for one thing naturally (e.g., just the phone number).
        - NEVER include "Uncle Verma's Response:" or any meta-text.
        - NEVER use "hey" in Emails.
        - DO NOT provide multiple options.
        
        SCAMMER MESSAGE TO RESPOND TO: "{user_message}"
        
        NOW WRITE YOUR REPLY AS THE VICTIM:
        """
        
        return await self._invoke_llm(prompt)

    async def generate_response(self, session_state: Dict, user_message: str, metadata: Any = None) -> Dict:
        """
        Orchestrate the conversation pipeline: Profiler -> Analyst -> Director -> Actor.
        Returns dialogue and metadata about conversation state.
        """
        # 1. PROFILER (First Turn Only)
        if "persona_profile" not in session_state:
            profile = await self.profiler_step(user_message, metadata)
            session_state["persona_profile"] = profile
        
        profile = session_state["persona_profile"]
        
        # Update history
        history = session_state.get("raw_history", [])
        history.append({"role": "scammer", "text": user_message})
        
        analyst_facts = await self.analyst_step(history, metadata)
        session_state["analyst_facts"] = analyst_facts
        
        stage_direction = await self.director_step(history, profile, analyst_facts, user_message, metadata)
        
        reply_text = await self.actor_step(session_state, user_message, stage_direction, metadata)
        
        # Update history
        history.append({"role": "victim", "text": reply_text})
        session_state["raw_history"] = history
        
        return {
            "reply": reply_text,
            "intelligence": {
                "strategy": stage_direction, 
                "persona": profile['name'],
                "money_flow": profile.get('money_flow', 'Unknown'),
                "analyst_facts": analyst_facts
            }
        }
