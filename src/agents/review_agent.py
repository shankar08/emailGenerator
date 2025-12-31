import json
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langsmith import traceable



class ReviewAgent:
    @staticmethod
    @traceable(run_type="llm")
    def run(state: Dict[str, Any], llm) -> Dict[str, Any]:
        draft = state.get("personalized_draft", {})
        tone = state.get("tone", "formal")
        system = (
            "You are an email reviewer. Check the email for grammar, clarity, and adherence to the requested tone. "
            "Return JSON with fields: ok (true/false), issues (list of strings), suggested_edits (full-body suggestion)."
        )
        template = "Tone: {tone}\n\nEmail Subject: {subject}\n\nEmail Body:\n{body}\n\nReturn the JSON."
        chain = ChatPromptTemplate.from_messages([
            ("system", system),
            ("user", template)
        ]) | llm | StrOutputParser()
        raw = chain.invoke({
            "tone": tone,
            "subject": draft.get("subject", ""),
            "body": draft.get("body", "")
        })
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"ok": True, "issues": [], "suggested_edits": draft.get("body", "")}
        return {"review": parsed}
