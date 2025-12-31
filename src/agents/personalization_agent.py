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
        body = (draft.get("body", "") or "")
        subject = (draft.get("subject", "") or "")

        # Replace placeholders
        for key, val in {
            "{{sender_name}}": sender_name,
            "{sender_name}": sender_name,
            "{{signature}}": default_signature,
            "{signature}": default_signature
        }.items():
            body = body.replace(key, val)
            subject = subject.replace(key, val)

        # Check for signature
        signature_patterns = ["best regards", "warm regards", "sincerely", "cheers"]
        body_lower = body.lower()
        signature_present = any(p in body_lower for p in signature_patterns)

        # Add signature if missing
        if not signature_present:
            body = body.strip() + f"\n\n{default_signature}\n{sender_name}"
        elif sender_name.lower() not in body_lower:
            body = body.strip() + f"\n{sender_name}"

        return {"personalized_draft": {"subject": subject.strip(), "body": body.strip()}}
