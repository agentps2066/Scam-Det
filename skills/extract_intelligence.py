import re
import requests
from typing import Optional, Dict

class IntelligenceExtractor:
    @staticmethod
    def extract_upi(text: str) -> Optional[str]:
        # Simple regex for UPI IDs
        upi_pattern = r'[a-zA-Z0-9.-]+@[a-zA-Z0-9.-]+'
        match = re.search(upi_pattern, text)
        return match.group(0) if match else None

    @staticmethod
    def extract_phone(text: str) -> Optional[str]:
        # Indian phone numbers
        phone_pattern = r'(?:\+91|91|0)?[6-9]\d{9}'
        match = re.search(phone_pattern, text)
        return match.group(0) if match else None

    @staticmethod
    def extract_url(text: str) -> Optional[str]:
        # Simple URL regex
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
        match = re.search(url_pattern, text)
        return match.group(0) if match else None

    @staticmethod
    def extract_bank_account(text: str) -> Optional[str]:
        # Look for 9-18 digit numbers (often labeled as Acc/Account/ABA)
        # Matches "Acc: 1234..." or just long strings of digits that aren't phones
        acc_pattern = r'\b\d{9,18}\b'
        match = re.search(acc_pattern, text)
        # Filter out if it looks like a phone (starts with 9/8/7/6 and is 10 digits)
        if match:
            val = match.group(0)
            if len(val) == 10 and val[0] in "6789":
                return None # Likely a phone number
            return val
        return None

    @classmethod
    def process_and_report(cls, text: str, session_id: str) -> Dict:
        intel = {
            "upi": cls.extract_upi(text),
            "phone": cls.extract_phone(text),
            "url": cls.extract_url(text),
            "bank_account": cls.extract_bank_account(text)
        }
        
        # Filter out None values
        found_intel = {k: v for k, v in intel.items() if v}
        
        if found_intel:
            import os
            import logging
            logger = logging.getLogger("honeypot")
            logger.debug(f"Intelligence extracted from session {session_id}: {found_intel}")
                
        return found_intel
