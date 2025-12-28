
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langsmith import traceable

class IntentDetectionAgent:
    @staticmethod
    @traceable(run_type="llm")
    def run(state: Dict[str, Any], llm) -> Dict[str, Any]:
        parsed = state.get("parsed", {})
        prompt = parsed.get("prompt_text", "")
        system = (
            "You are an email intent classifier. Classify the user's intent into one of: "
            "outreach, follow-up, apology, internal_update, ask_for_meeting, introduction, promotion, other. "
            "Respond with only the single label."
        )
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", system),
            ("user", "{text}")
        ])
        chain = chat_prompt | llm | StrOutputParser()
        decision = chain.invoke({"text": prompt}).strip().lower()
        known = {"outreach","follow-up","apology","internal_update","ask_for_meeting","introduction","promotion","other"}
        if decision not in known:
            decision = "other"
        return {"intent": decision}
