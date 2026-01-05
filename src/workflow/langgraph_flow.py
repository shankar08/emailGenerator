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

from src.agents.input_parser_agent import InputParserAgent
from src.agents.intent_detection_agent import IntentDetectionAgent
from src.agents.tone_stylist_agent import ToneStylistAgent
from src.agents.draft_writer_agent import DraftWriterAgent
from src.agents.personalization_agent import PersonalizationAgent
from src.agents.review_agent import ReviewAgent
from src.agents.router_agent import RouterAgent

from src.integrations.llm_client import make_openai_llm
from src.memory.store import get_profile, upsert_profile

import time
from copy import deepcopy
import uuid
from langchain_core.messages import HumanMessage


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
    traces: List[dict]


# ===========================
# Instantiate OpenAI LLM
# ===========================
LLM = make_openai_llm(
    model="gpt-4o-mini",
    temperature=0.15
)



# ===========================
# Tracing decorator( Core Piece)
# ===========================
def traced_node(name: str):
    """
    Decorator for LangGraph nodes that logs
    input, output, and execution time.
    """
    def decorator(fn):
        def wrapper(state: EmailState) -> EmailState:
            start = time.time()

            # Snapshot input (safe shallow copy)
            input_snapshot = deepcopy(
                {k: v for k, v in state.items() if k != "messages"}
            )

            result = fn(state)

            duration_ms = round((time.time() - start) * 1000, 2)

            trace = {
                "agent": name,
                "duration_ms": duration_ms,
                "input_keys": list(input_snapshot.keys()),
                "output_keys": list(result.keys()),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            result.setdefault("traces", []).append(trace)

            # Optional console logging
            print(f"[TRACE] {name} | {duration_ms}ms")

            return result

        return wrapper
    return decorator

# ===========================
# Workflow nodes
# ===========================
@traced_node("input_parser")
def node_input_parser(state: EmailState) -> EmailState:
    state["user_profile"] = get_profile("default") or {}
    state.setdefault("rewrite_count", 0)
    state.update(InputParserAgent.run(state))
    return state


@traced_node("intent_detection")
def node_intent_detection(state: EmailState) -> EmailState:
    state.update(IntentDetectionAgent.run(state, LLM))
    return state


@traced_node("tone_stylist")
def node_tone_stylist(state: EmailState) -> EmailState:
    state.update(ToneStylistAgent.run(state))
    return state

@traced_node("draft_writer")
def node_draft_writer(state: EmailState) -> EmailState:
    state.update(DraftWriterAgent.run(state, LLM))
    return state

@traced_node("tone_stylist")
def node_tone_stylist(state: EmailState) -> EmailState:
    state.update(ToneStylistAgent.run(state))
    return state


@traced_node("personalization")
def node_personalization(state: EmailState) -> EmailState:
    state.update(PersonalizationAgent.run(state))

    profile = state.get("user_profile", {})
    draft = state.get("personalized_draft")

    if draft:
        profile.setdefault("sent_examples", []).append(draft)
        upsert_profile("default", profile)

    return state


@traced_node("review")
def node_review(state: EmailState) -> EmailState:
    state.update(ReviewAgent.run(state, LLM))
    return state

@traced_node("router")
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
def run_email_workflow(user_text: str):
    """
    Entry point for UI / API usage.
    Adds required configurable keys for LangGraph checkpointer.
    """
    thread_id = str(uuid.uuid4())

    initial_state = {
        "messages": [HumanMessage(content=user_text)]
    }

    return email_planner.invoke(
        initial_state,
        config={
            "configurable": {
                "thread_id": thread_id
            }
        }
    )