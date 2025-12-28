from typing import Dict, Any
from langsmith import traceable


DEFAULT_SENDER_NAME = "SP"

class PersonalizationAgent:
    @staticmethod
    @traceable(run_type="llm")
    def run(state: Dict[str, Any]) -> Dict[str, Any]:
        draft = state.get("draft", {})
        profile = state.get("user_profile", {})
        default_signature = profile.get("signature", "Best regards,")
        sender_name = DEFAULT_SENDER_NAME
        body = draft.get("body", "") or ""
        subject = draft.get("subject", "") or ""
        body = (
            body.replace("{{sender_name}}", sender_name)
                .replace("{sender_name}", sender_name)
                .replace("{{signature}}", default_signature)
                .replace("{signature}", default_signature)
        )
        subject = (
            subject.replace("{{sender_name}}", sender_name)
                   .replace("{sender_name}", sender_name)
        )
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        greeting_prefixes = ("dear ", "hi ", "hello ")
        if lines and not lines[0].lower().startswith(greeting_prefixes):
            pass
        signature_patterns = ["best regards", "warm regards", "sincerely", "cheers"]
        body_lower = body.lower()
        signature_present = any(pattern in body_lower for pattern in signature_patterns)
        if not signature_present:
            body = body.strip() + f"\n\n{default_signature}\n{sender_name}"
        else:
            if sender_name.lower() not in body_lower:
                body = body.strip() + f"\n{sender_name}"
        return {"personalized_draft": {"subject": subject.strip(), "body": body.strip()}}
