# -*- coding: utf-8 -*-
"""
langgraph_flow.py

Wires agents into a LangGraph StateGraph and exposes a run_email_workflow helper.
Uses OpenAI LLM for email drafting workflow.
"""

from typing import TypedDict, List, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

from langchain_core.messages import HumanMessage, BaseMessage

from agents.input_parser_agent import InputParserAgent
from agents.intent_detection_agent import IntentDetectionAgent
from agents.tone_stylist_agent import ToneStylistAgent
from agents.draft_writer_agent import DraftWriterAgent
from agents.personalization_agent import PersonalizationAgent
from agents.review_agent import ReviewAgent
from agents.router_agent import RouterAgent

from integrations.llm_client import make_openai_llm
from memory.json_memory import get_profile, upsert_profile


# ===========================
# Workflow state
# ===========================
class EmailState(TypedDict, total=False):
    messages: List[BaseMessage]
    parsed: dict
    intent: str
    tone: str
    tone_instructions: str
    draft: dict
    personalized_draft: dict
    review: dict
    user_profile: dict
    next_agent: str
    rewrite_count: int


# ===========================
# Instantiate OpenAI LLM
# ===========================
LLM = make_openai_llm(
    model="gpt-4o-mini",
    temperature=0.15
)


# ===========================
# Workflow nodes
# ===========================
def node_input_parser(state: EmailState) -> EmailState:
    state["user_profile"] = get_profile("default") or {}
    state.setdefault("rewrite_count", 0)
    state.update(InputParserAgent.run(state))
    return state


def node_intent_detection(state: EmailState) -> EmailState:
    state.update(IntentDetectionAgent.run(state, LLM))
    return state


def node_tone_stylist(state: EmailState) -> EmailState:
    state.update(ToneStylistAgent.run(state))
    return state


def node_draft_writer(state: EmailState) -> EmailState:
    state.update(DraftWriterAgent.run(state, LLM))
    return state


def node_personalization(state: EmailState) -> EmailState:
    state.update(PersonalizationAgent.run(state))

    profile = state.get("user_profile", {})
    draft = state.get("personalized_draft")

    if draft:
        profile.setdefault("sent_examples", []).append(draft)
        upsert_profile("default", profile)

    return state


def node_review(state: EmailState) -> EmailState:
    state.update(ReviewAgent.run(state, LLM))
    return state


def node_router(state: EmailState) -> EmailState:
    state.update(RouterAgent.run(state))
    return state


# ===========================
# Router logic
# ===========================
def router_decision(state: EmailState) -> str:
    """
    Controls graph flow.
    Prevents infinite rewrite loops.
    """
    next_agent = state.get("next_agent")

    if next_agent == "rewrite":
        state["rewrite_count"] = state.get("rewrite_count", 0) + 1
        if state["rewrite_count"] <= 1:
            return "draft_writer"

    return END


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

workflow.set_entry_point("input_parser")

workflow.add_edge("input_parser", "intent_detection")
workflow.add_edge("intent_detection", "tone_stylist")
workflow.add_edge("tone_stylist", "draft_writer")
workflow.add_edge("draft_writer", "personalization")
workflow.add_edge("personalization", "review")
workflow.add_edge("review", "router")

workflow.add_conditional_edges(
    "router",
    router_decision,
    {
        "draft_writer": "draft_writer",
        END: END,
    },
)

# ===========================
# Compile workflow
# ===========================
checkpointer = InMemorySaver()
email_planner = workflow.compile(checkpointer=checkpointer)


# ===========================
# Public helper
# ===========================
def run_email_workflow(user_text: str) -> EmailState:
    """
    Entry point for UI / API usage.
    """
    initial_state: EmailState = {
        "messages": [HumanMessage(content=user_text)]
    }

    return email_planner.invoke(initial_state)