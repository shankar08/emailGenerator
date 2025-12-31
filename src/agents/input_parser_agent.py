from typing import Dict, Any
import re
from langsmith import traceable
from langchain_core.messages import BaseMessage


class InputParserAgent:
    @staticmethod
    @traceable(run_type="llm")
    def run(state: Dict[str, Any]) -> Dict[str, Any]:
        messages = state.get("messages", [])
        if not messages:
            return {"parsed": {}}

        last_msg = messages[-1]

        # ✅ Correctly extract message content
        if isinstance(last_msg, BaseMessage):
            text = last_msg.content
        elif isinstance(last_msg, dict):
            text = last_msg.get("content", "")
        else:
            text = str(last_msg)

        def extract(pattern, text, group=1, flags=re.I):
            match = re.search(pattern, text, flags)
            return match.group(group).strip() if match else None

        recipient_name = extract(r"to[:\-]\s*([A-Za-z .,@]+)", text)
        preferred_tone = extract(
            r"tone[:\-]\s*(formal|casual|assertive|friendly)",
            text
        )
        length = extract(r"length[:\-]\s*(short|long|medium|\d+\s*words)", text)

        constraints = {"length": length} if length else {}

        parsed = {
            "prompt_text": text,
            "recipient_name": recipient_name,
            "recipient_role": None,
            "preferred_tone": preferred_tone,
            "constraints": constraints,
        }

        return {"parsed": parsed}