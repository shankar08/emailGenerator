import json
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langsmith import traceable


DEFAULT_SENDER_NAME = "SP"


class DraftWriterAgent:
    @staticmethod
    @traceable(run_type="llm")
    def run(state: Dict[str, Any], llm, max_output_tokens: int = 512) -> Dict[str, Any]:
        parsed = state.get("parsed", {})
        user_profile = state.get("user_profile", {})
        system = (
            "You are an expert email writer. Given the user's intent, tone instructions, and recipient details, "
            "produce a concise, well-structured email draft. Output JSON with keys: subject, body."
        )
        template = (
            "User Prompt: {prompt}\n\n"
            "Intent: {intent}\n"
            "Tone Instructions: {tone_instructions}\n"
            "Sender Profile: name: {sender_name}, company: {profile_company}\n"
            "Recipient: {recipient}\n"
            "Constraints: {constraints}\n\n"
            "Return a JSON object exactly with fields: subject, body. Always ensure sender name is 'SP'."
        )
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", system),
            ("user", template)
        ])
        chain = chat_prompt | llm | StrOutputParser()
        payload = {
            "prompt": parsed.get("prompt_text", ""),
            "intent": state.get("intent", "other"),
            "tone_instructions": state.get("tone_instructions", ""),
            "sender_name": user_profile.get("name") or DEFAULT_SENDER_NAME,
            "profile_company": user_profile.get("company", ""),
            "recipient": parsed.get("recipient_name", ""),
            "constraints": str(parsed.get("constraints", {}))
        }
        raw = chain.invoke(payload)
        try:
            parsed_json = json.loads(raw)
            subject = parsed_json.get("subject", "")
            body = parsed_json.get("body", "")
        except Exception:
            subject = (parsed.get("prompt_text", "")[:60] + "...") if parsed.get("prompt_text") else "New Email"
            body = raw
        return {"draft": {"subject": subject.strip(), "body": body.strip()}}
