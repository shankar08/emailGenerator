
from typing import Dict, Any
import re
from langsmith import traceable

class InputParserAgent:
    @staticmethod
    @traceable(run_type="llm")
    def run(state: Dict[str, Any]) -> Dict[str, Any]:
        messages = state.get("messages", [])
        if not messages:
            return {"parsed": {}}
        last = messages[-1]
        text = getattr(last, "content", str(last))
        recipient_name = None
        recipient_role = None
        preferred_tone = None
        constraints = {}

        m_to = re.search(r"to[:\-]\s*([A-Za-z .,@]+)", text, re.I)
        if m_to:
            recipient_name = m_to.group(1).strip()
        m_tone = re.search(r"tone[:\-]\s*(formal|casual|assertive|friendly)", text, re.I)
        if m_tone:
            preferred_tone = m_tone.group(1).lower()
        m_len = re.search(r"length[:\-]\s*(short|long|medium|\d+\s*words)", text, re.I)
        if m_len:
            constraints["length"] = m_len.group(1)

        parsed = {
            "prompt_text": text,
            "recipient_name": recipient_name,
            "recipient_role": recipient_role,
            "preferred_tone": preferred_tone,
            "constraints": constraints
        }
        return {"parsed": parsed}
