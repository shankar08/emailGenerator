"""
Modular agent implementations for the LangGraph workflow.
"""
from typing import Dict, Any
import json, re
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langsmith import traceable

# Load tone samples
TONE_SAMPLES_PATH = Path(__file__).parent.parent.parent / "data" / "tone_samples.json"
with open(TONE_SAMPLES_PATH, "r", encoding="utf-8") as f:
    TONE_SAMPLES = json.load(f)

# Default sender name
DEFAULT_SENDER_NAME = "SP"

@traceable(run_type="llm")
def input_parser_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    messages = state.get("messages", [])
    if not messages:
        return {"parsed": {}}
    last = messages[-1]
    text = getattr(last, "content", str(last))
    recipient_name = None
    recipient_role = None
    preferred_tone = None
    constraints = {}

    m_to = re.search(r"to[:\\-]\\s*([A-Za-z .,@]+)", text, re.I)
    if m_to:
        recipient_name = m_to.group(1).strip()
    m_tone = re.search(r"tone[:\\-]\\s*(formal|casual|assertive|friendly)", text, re.I)
    if m_tone:
        preferred_tone = m_tone.group(1).lower()
    m_len = re.search(r"length[:\\-]\\s*(short|long|medium|\\d+\\s*words)", text, re.I)
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

@traceable(run_type="llm")
def intent_detection_agent(state: Dict[str, Any], llm) -> Dict[str, Any]:
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

@traceable(run_type="llm")
def tone_stylist_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    parsed = state.get("parsed") or {}
    prefer = parsed.get("preferred_tone") or state.get("user_profile", {}).get("preferred_tone", "formal")
    
    tone = prefer if prefer in TONE_SAMPLES else "formal"
    tone_instructions = TONE_SAMPLES.get(tone, TONE_SAMPLES["formal"])
    
    examples = {
       "formal": "Example: Hi Emma,\nI hope this message finds you well. I am writing to invite you to our upcoming meeting. Please confirm your availability. Best regards, SP.",
       "casual": "Example: Hey Emma!\nHope you're doing well! I wanted to invite you to our Secret Santa party at my place on Friday. Let me know if you can make it! Cheers, SP.",
       "assertive": "Example: Emma,\nYou are invited to the Secret Santa party on Friday at 7 PM. Please confirm your attendance by Wednesday. Best regards, SP."
    }
    
    tone_instructions += f"\n\n{examples[tone]}"
    
    return {"tone": tone, "tone_instructions": tone_instructions}

@traceable(run_type="llm")
def draft_writer_agent(state: Dict[str, Any], llm, max_output_tokens: int = 512) -> Dict[str, Any]:
    parsed = state.get("parsed", {})
    intent = state.get("intent", "other")
    tone_info = state.get("tone_instructions", "")
    user_profile = state.get("user_profile", {})
    
    sender_name = user_profile.get("name") or DEFAULT_SENDER_NAME
    system = ("You are an expert email writer. Given the user's intent, tone instructions, and recipient details, "
              "produce a concise, well-structured email draft. Output JSON with keys: subject, body.")
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
    profile_summary = f"{user_profile.get('company','')}"
    recipient = parsed.get("recipient_name") or ""
    constraints = parsed.get("constraints") or {}
    raw = chain.invoke({
        "prompt": parsed.get("prompt_text", ""),
        "intent": intent,
        "tone_instructions": tone_info,
        "sender_name": sender_name,
        "profile_company": profile_summary,
        "recipient": recipient,
        "constraints": str(constraints)
    })
    try:
        parsed_json = json.loads(raw)
        subject = parsed_json.get("subject", "")
        body = parsed_json.get("body", "")
    except Exception:
        body = raw
        subject = (parsed.get("prompt_text", "")[:60] + "...") if parsed.get("prompt_text") else "New Email"
    return {"draft": {"subject": subject.strip(), "body": body.strip()}}

@traceable(run_type="llm")
def personalization_agent(state: Dict[str, Any]) -> Dict[str, Any]:
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

@traceable(run_type="llm")
def review_agent(state: Dict[str, Any], llm) -> Dict[str, Any]:
    draft = state.get("personalized_draft", {})
    tone = state.get("tone", "formal")
    system = ("You are an email reviewer. Check the email for grammar, clarity, and adherence to the requested tone. "
              "Return JSON with fields: ok (true/false), issues (list of strings), suggested_edits (full-body suggestion).")
    template = "Tone: {tone}\n\nEmail Subject: {subject}\n\nEmail Body:\n{body}\n\nReturn the JSON."
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("user", template)
    ])
    chain = chat_prompt | llm | StrOutputParser()
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

@traceable(run_type="llm")
def router_agent(state):
    review = state.get("review", {})
    retry_count = state.get("retry_count", 0)
    max_retries = 3

    if not review:
        return {"route": "done"}
    if review.get("ok", True):
        return {"route": "done"}
    if retry_count >= max_retries:
        return {
            "route": "done",
            "reason": "max_retries_exceeded",
            "issues": review.get("issues", []),
            "retry_count": retry_count,
        }

    return {
        "route": "rewrite",
        "issues": review.get("issues", []),
        "retry_count": retry_count + 1,
    }
