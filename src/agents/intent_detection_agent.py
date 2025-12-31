
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langsmith import traceable


class IntentDetectionAgent:
    @staticmethod
    @traceable(run_type="llm")
    def run(state: Dict[str, Any], llm) -> Dict[str, Any]:
        prompt = state.get("parsed", {}).get("prompt_text", "")
        system = (
            "You are an email intent classifier. Classify the user's intent into one of: "
            "outreach, follow-up, apology, internal_update, ask_for_meeting, introduction, promotion, other. "
            "Respond with only the single label."
        )
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", system),
            ("user", "{text}")
        ])
        decision = (chat_prompt | llm | StrOutputParser()).invoke({"text": prompt}).strip().lower()
        if decision not in {
            "outreach", "follow-up", "apology", "internal_update", "ask_for_meeting", "introduction", "promotion", "other"
        }:
            decision = "other"
        return {"intent": decision}
