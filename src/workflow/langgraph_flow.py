# -*- coding: utf-8 -*-
"""
langgraph_flow.py

Wires agents into a LangGraph StateGraph and exposes a run_email_workflow helper.
Uses OpenAI LLM for email drafting workflow.
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, BaseMessage
from typing import TypedDict, List, Optional

from agents.agents import (
    input_parser_agent,
    intent_detection_agent,
    tone_stylist_agent,
    draft_writer_agent,
    personalization_agent,
    review_agent,
    router_agent
)
from integrations.llm_client import make_openai_llm
from memory.json_memory import get_profile, upsert_profile

# ===========================
# Workflow state
# ===========================
class EmailState(TypedDict):
    messages: List[BaseMessage]
    parsed: dict
    intent: str
    tone: str
    tone_instructions: str
    draft: dict
    personalized_draft: dict
    review: dict
    user_profile: dict
    next_agent: Optional[str]

# ===========================
# Instantiate OpenAI LLM
# ===========================
LLM = make_openai_llm(model="gpt-3.5-turbo", temperature=0.15)

# ===========================
# Workflow nodes
# ===========================
def node_input_parser(state: EmailState):
    res = input_parser_agent(state)
    state["user_profile"] = get_profile("default")
    state.update(res)
    return {"messages": state.get("messages"), **res}

def node_intent_detection(state: EmailState):
    res = intent_detection_agent(state, LLM)
    state.update(res)
    return {"messages": state.get("messages"), **res}

def node_tone_stylist(state: EmailState):
    res = tone_stylist_agent(state)
    state.update(res)
    return {"messages": state.get("messages"), **res}

def node_draft_writer(state: EmailState):
    res = draft_writer_agent(state, LLM)
    state.update(res)
    return {"messages": state.get("messages"), **res}

def node_personalization(state: EmailState):
    res = personalization_agent(state)
    state.update(res)
    profile = state.get("user_profile", {})
    profile.setdefault("sent_examples", []).append(state.get("personalized_draft"))
    upsert_profile("default", profile)
    return {"messages": state.get("messages"), **res}

def node_review(state: EmailState):
    res = review_agent(state, LLM)
    state.update(res)
    return {"messages": state.get("messages"), **res}

def node_router(state: EmailState):
    res = router_agent(state)
    state.update(res)
    return {"messages": state.get("messages"), "next_agent": state.get("next_agent")}

def node_end(state: EmailState):
    """Dummy end node."""
    return {"messages": state.get("messages")}

# ===========================
# Build workflow
# ===========================
workflow = StateGraph(EmailState)

workflow.add_node("input_parser", node_input_parser)
workflow.add_node("intent_detection", node_intent_detection)
workflow.add_node("tone_stylist", node_tone_stylist)
workflow.add_node("draft_writer", node_draft_writer)
workflow.add_node("personalization", node_personalization)
workflow.add_node("review", node_review)
workflow.add_node("router", node_router)
workflow.add_node("end", node_end)

workflow.set_entry_point("input_parser")
workflow.add_edge("input_parser", "intent_detection")
workflow.add_edge("intent_detection", "tone_stylist")
workflow.add_edge("tone_stylist", "draft_writer")
workflow.add_edge("draft_writer", "personalization")
workflow.add_edge("personalization", "review")
workflow.add_edge("review", "router")

# ===========================
# Router logic
# ===========================
def router_decision(state: EmailState):
    nxt = state.get("next_agent")
    if nxt == "rewrite":
        return "draft_writer"
    return "end"

workflow.add_conditional_edges(
    "router",
    router_decision,
    {
        "draft_writer": "draft_writer",
        "end": "end"
    }
)

# ===========================
# Checkpointer
# ===========================
checkpointer = InMemorySaver()
email_planner = workflow.compile(checkpointer=checkpointer)

# ===========================
# Run workflow helper
# ===========================
def run_email_workflow(user_text: str):
    state = {"messages": [{"content": user_text}], "flow": []}
    
    # Agents called in order
    agents = [
        ("input_parser_agent", input_parser_agent),
        ("intent_detection_agent", lambda s: intent_detection_agent(s, llm=make_openai_llm())),
        ("tone_stylist_agent", tone_stylist_agent),
        ("draft_writer_agent", lambda s: draft_writer_agent(s, llm=make_openai_llm())),
        ("personalization_agent", personalization_agent),
        ("review_agent", lambda s: review_agent(s, llm=make_openai_llm())),
        ("router_agent", router_agent)
    ]
    
    for name, fn in agents:
        output = fn(state)
        state.update(output)
        state["flow"].append({"agent": name, "output": output})
    
    return state

