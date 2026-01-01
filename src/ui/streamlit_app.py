# -*- coding: utf-8 -*-
"""
Streamlit app for AI Powered Email Generator
Includes LLM-based evaluation with GitHub-synced persistence.
"""

import json
import re
import tempfile
from datetime import datetime

import streamlit as st
import openai
from langsmith import traceable

from workflow.langgraph_flow import run_email_workflow
from integrations.llm_client import make_openai_llm
from eval.eval_runner import validate_scores

from memory.store import (
    get_profile,
    upsert_profile,
    save_eval,
    get_eval_history,
)

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def safe_json_loads(text: str) -> dict:
    """Safely parse JSON, stripping markdown fences."""
    if not text:
        raise ValueError("Empty response from judge")

    cleaned = re.sub(r"```(?:json)?", "", text)
    cleaned = cleaned.replace("```", "").strip()

    return json.loads(cleaned)


# --------------------------------------------------
# LLM Judge
# --------------------------------------------------

@traceable(run_type="evaluation")
def judge_email(user_input: str, tone: str, subject: str, body: str) -> dict:
    llm = make_openai_llm(model="gpt-4o", temperature=0)

    prompt = f"""
                You are an expert email reviewer.

                Evaluate the GENERATED EMAIL against the USER REQUEST.

                IMPORTANT:
                - Scores MUST be integers from 1 to 10 ONLY.
                - Do NOT use any other scale.
                - Do NOT include decimals.
                - Do NOT exceed 10.

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


# --------------------------------------------------
# Streamlit App
# --------------------------------------------------

def main():
    st.set_page_config(page_title="AI Powered Email Generator", layout="wide")
    st.title("AI Powered Email Generator")

    tabs = st.tabs(["Profile", "Compose & Draft", "Eval History"])

    # ==================================================
    # Profile Tab
    # ==================================================
    with tabs[0]:
        st.header("User Profile")

        profile = get_profile("default")

        with st.form("profile_form"):
            name = st.text_input(
                "Sender name",
                value=profile.get("name", "SP"),
            )
            company = st.text_input(
                "Company",
                value=profile.get("company", "True Startup"),
            )

            submitted = st.form_submit_button("Save profile")

            if submitted:
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

    # ==================================================
    # Compose & Draft Tab
    # ==================================================
    with tabs[1]:
        st.header("Compose & Draft")
        left, right = st.columns([2, 3])

        # ------------------------------
        # Input
        # ------------------------------
        with left:
            st.subheader("Compose Email")

            mode = st.radio("Input mode", ["Text", "Voice"], index=0)
            user_text = ""

            if mode == "Text":
                user_text = st.text_area(
                    "Describe your email intent",
                    height=200,
                )
            else:
                st.info("Upload an audio file (WAV, MP3, M4A, MP4).")

                if "voice_text" not in st.session_state:
                    st.session_state.voice_text = ""

                audio_file = st.file_uploader(
                    "Upload audio",
                    type=["wav", "mp3", "m4a", "mp4"],
                )

                if audio_file:
                    suffix = "." + audio_file.name.split(".")[-1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(audio_file.read())
                        audio_path = tmp.name

                    client = openai.OpenAI()
                    with open(audio_path, "rb") as f:
                        transcript = client.audio.transcriptions.create(
                            file=f,
                            model="gpt-4o-transcribe",
                            language="en",
                        )

                    st.session_state.voice_text = getattr(transcript, "text", "")
                    st.write("Transcription:")
                    st.write(st.session_state.voice_text)

                user_text = st.session_state.voice_text

            tone_choice = st.selectbox(
                "Tone (optional)",
                ["(profile)", "formal", "casual", "assertive"],
            )

            if st.button("Generate Email Draft"):
                if not user_text:
                    st.warning("Please provide email intent.")
                    st.stop()

                extra = f"\n\ntone: {tone_choice}" if tone_choice != "(profile)" else ""
                prompt_text = user_text + extra

                with st.spinner("Generating email draft..."):
                    result = run_email_workflow(prompt_text)

                st.session_state.last_result = result
                st.success("Email draft generated.")

                draft = result.get("personalized_draft") or result.get("draft") or {}

                with st.spinner("Evaluating draft..."):
                    scores = judge_email(
                        user_input=prompt_text,
                        tone=tone_choice,
                        subject=draft.get("subject", ""),
                        body=draft.get("body", ""),
                    )

                st.session_state.last_eval = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "scores": scores,
                }

                if "error" not in scores:
                    save_eval(
                        prompt=prompt_text,
                        draft=draft,
                        scores=scores,
                    )
                    st.success("Email evaluated and saved.")
                else:
                    st.error("Evaluation failed. See Eval History for details.")

        # ------------------------------
        # Draft Preview
        # ------------------------------
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
                mime="text/plain",
                disabled=not bool(subject_edit or body_edit),
            )

            if st.button("Save to Profile History", disabled=not last):
                prof = get_profile("default")
                prof.setdefault("sent_examples", []).append(
                    {"subject": subject_edit, "body": body_edit}
                )
                upsert_profile("default", prof)
                st.success("Draft saved to profile history.")

    # ==================================================
    # Evaluation History Tab
    # ==================================================
    with tabs[2]:
        st.header("Evaluation History")

        history = get_eval_history(limit=25)

        if not history:
            st.info("No evaluations recorded yet.")
            return

        for record in history:
            scores = record.get("scores", {})

            with st.expander(
                f"{record['timestamp']} • Overall {scores.get('overall_score', 'N/A')}"
            ):
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

                    with st.expander("Raw JSON"):
                        st.json(scores)


if __name__ == "__main__":
    main()