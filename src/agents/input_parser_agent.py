
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
        text = str(messages[-1].get("content", messages[-1]))

        def extract(pattern, text, group=1, flags=re.I):
            match = re.search(pattern, text, flags)
            return match.group(group).strip() if match else None

        recipient_name = extract(r"to[:\-]\s*([A-Za-z .,@]+)", text)
        preferred_tone = extract(r"tone[:\-]\s*(formal|casual|assertive|friendly)", text)
        length = extract(r"length[:\-]\s*(short|long|medium|\d+\s*words)", text)
        constraints = {"length": length} if length else {}

        parsed = {
            "prompt_text": text,
            "recipient_name": recipient_name,
            "recipient_role": None,
            "preferred_tone": preferred_tone,
            "constraints": constraints
        }
        return {"parsed": parsed}
