# -*- coding: utf-8 -*-
"""
Streamlit app for AI Powered Email Generator
Includes:
- Multi-agent email generation
- Audio input support (.m4a, .mp3, .wav, .mp4)
- Immediate display of user messages
- Per-agent execution timing and evaluation
"""

import json
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
import sys
import os

import streamlit as st
import openai

# ----------- Path bootstrap (REQUIRED for Streamlit) -----------
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# ---------------------------------------------------------------

from src.workflow.langgraph_flow import run_email_workflow
from src.integrations.llm_client import make_openai_llm
from src.eval.eval_runner import validate_scores
from src.memory.store import get_profile, upsert_profile, save_eval, get_eval_history

# -----------------------------
# Helpers
# -----------------------------
def safe_json_loads(text: str) -> dict:
    """Safely parse JSON, stripping markdown fences."""
    if not text:
        raise ValueError("Empty response from judge")

    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.DOTALL)
    cleaned = cleaned.replace("```", "").strip()

    return json.loads(cleaned)


# -----------------------------
# LLM Judge
# -----------------------------
def judge_email(user_input: str, tone: str, subject: str, body: str) -> dict:
    llm = make_openai_llm(model="gpt-4o", temperature=0)

    prompt = f"""
You are an expert email reviewer.

Evaluate the GENERATED EMAIL against the USER REQUEST.

IMPORTANT:
- Scores MUST be integers from 1 to 10 ONLY
- Do NOT use decimals or other scales

USER REQUEST:
{user_input}

REQUESTED TONE:
{tone}

GENERATED EMAIL:
Subject: {subject}

{body}

Return ONLY valid JSON with:
- intent_accuracy
- tone_alignment
- clarity
- professionalism
- completeness
- grammar
- overall_score
- explanation
"""

    response = llm.invoke(prompt)

    try:
        scores = safe_json_loads(response.content)
    except Exception as e:
        return {
            "error": "JSON Parse Error",
            "raw_output": response.content,
            "exception": str(e),
        }

    if not validate_scores(scores):
        return {
            "error": "Invalid score scale",
            "raw_output": scores,
        }

    return scores


# -----------------------------
# Streamlit App
# -----------------------------
def main():
    st.set_page_config(page_title="AI Powered Email Generator", layout="wide")
    st.title("AI Powered Email Generator")

    tabs = st.tabs(["Profile", "Compose & Draft", "Eval History"])

    # -----------------------------
    # Profile Tab
    # -----------------------------
    with tabs[0]:
        st.header("User Profile")
        profile = get_profile("default")

        with st.form("profile_form"):
            name = st.text_input("Sender name", profile.get("name", "SP"))
            company = st.text_input("Company", profile.get("company", "True Startup"))

            if st.form_submit_button("Save profile"):
                upsert_profile(
                    "default",
                    {
                        "name": name,
                        "company": company,
                        "preferred_tone": profile.get("preferred_tone", "formal"),
                        "sent_examples": profile.get("sent_examples", []),
                    },
                )
                st.success("Profile saved successfully.")

    # -----------------------------
    # Compose & Draft Tab
    # -----------------------------
    with tabs[1]:
        st.header("Compose & Draft")
        left, right = st.columns([2, 3])

        # -----------------------------
        # Input Section
        # -----------------------------
        with left:
            st.subheader("Compose Email")

            mode = st.radio("Input mode", ["Text", "Voice"], index=0)
            user_text = ""

            if mode == "Text":
                user_text = st.text_area("Describe your email intent", height=200)
            else:
                audio_file = st.file_uploader(
                    "Upload audio (.m4a, .mp3, .wav, .mp4)", 
                    type=["m4a", "mp3", "wav", "mp4"]
                )
                if audio_file:
                    suffix = "." + audio_file.name.split(".")[-1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(audio_file.read())
                        tmp.flush()
                        tmp_path = tmp.name

                    st.info(f"Saved temporary audio file: {tmp_path}")

                    try:
                        client = openai.OpenAI()
                        with open(tmp_path, "rb") as f:
                            transcript = client.audio.transcriptions.create(
                                file=f,
                                model="gpt-4o-transcribe",
                                language="en",
                            )
                        user_text = transcript.text
                        st.write("Transcription:")
                        st.write(user_text)
                    except openai.error.OpenAIError as e:
                        st.error(f"Transcription failed: {e}")
                        st.stop()

            tone_choice = st.selectbox(
                "Tone (optional)",
                ["(profile)", "formal", "casual", "assertive"],
            )

            if st.button("Generate Email Draft"):
                if not user_text:
                    st.warning("Please provide email intent.")
                    st.stop()

                prompt_text = (
                    user_text
                    if tone_choice == "(profile)"
                    else user_text + f"\n\ntone: {tone_choice}"
                )

                # -----------------------------
                # Run workflow
                # -----------------------------
                with st.spinner("Generating email draft..."):
                    result = run_email_workflow(prompt_text)

                st.session_state.last_result = result
                st.success("Email draft generated.")

                # -----------------------------
                # Agent Execution Timing
                # -----------------------------
                st.subheader("Agent Execution Trace")
                traces = result.get("traces", [])
                if not traces:
                    st.info("No trace data available.")
                else:
                    for trace in traces:
                        duration_sec = round(trace["duration_ms"] / 1000, 2)
                        with st.expander(f"{trace['agent']} • {duration_sec} s", expanded=False):
                            st.markdown(f"**Agent:** {trace['agent']}")
                            st.markdown(f"**Duration:** {duration_sec} seconds")
                            st.markdown(f"**Timestamp:** {trace['timestamp']}")
                            st.markdown("**Input Keys:**")
                            st.code(", ".join(trace.get("input_keys", [])))
                            st.markdown("**Output Keys:**")
                            st.code(", ".join(trace.get("output_keys", [])))

                # -----------------------------
                # Evaluation
                # -----------------------------
                draft = result.get("personalized_draft") or result.get("draft") or {}

                with st.spinner("Evaluating email..."):
                    scores = judge_email(
                        user_input=prompt_text,
                        tone=tone_choice,
                        subject=draft.get("subject", ""),
                        body=draft.get("body", ""),
                    )

                st.session_state.last_eval = scores

                if "error" not in scores:
                    save_eval(prompt=prompt_text, draft=draft, scores=scores)
                    st.success("Email evaluated and saved.")
                else:
                    st.error("Evaluation failed.")

        # -----------------------------
        # Draft Preview
        # -----------------------------
        with right:
            st.subheader("Draft & Actions")
            last = st.session_state.get("last_result")
            if last:
                draft = last.get("personalized_draft") or last.get("draft") or {}
                subject = draft.get("subject", "")
                body = draft.get("body", "")
            else:
                subject, body = "", ""
                st.info("No email generated yet.")

            subject_edit = st.text_input("Subject", subject)
            body_edit = st.text_area("Body", body, height=400)

            st.download_button(
                "Export as .txt",
                data=f"Subject: {subject_edit}\n\n{body_edit}",
                file_name="email_draft.txt",
            )

    # -----------------------------
    # Eval History Tab
    # -----------------------------
    with tabs[2]:
        st.header("Evaluation History")
        history = get_eval_history(limit=25)
        if not history:
            st.info("No evaluations recorded yet.")
        else:
            for record in history:
                scores = record.get("scores", {})
                with st.expander(f"{record['timestamp']} • Overall {scores.get('overall_score', 'N/A')}"):
                    st.markdown("### Prompt")
                    st.code(record["prompt"])
                    st.markdown("### Email Draft")
                    st.markdown(f"**Subject:** {record['subject']}")
                    st.text_area("Body", record["body"], height=200, disabled=True)

                    if "error" in scores:
                        st.error("Evaluation failed")
                        st.json(scores)
                    else:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Intent", scores["intent_accuracy"])
                        col2.metric("Tone", scores["tone_alignment"])
                        col3.metric("Clarity", scores["clarity"])
                        col1.metric("Professionalism", scores["professionalism"])
                        col2.metric("Completeness", scores["completeness"])
                        col3.metric("Grammar", scores["grammar"])
                        st.divider()
                        st.metric("Overall Score", scores["overall_score"])
                        st.markdown("**Judge Explanation**")
                        st.write(scores.get("explanation", ""))


if __name__ == "__main__":
    main()