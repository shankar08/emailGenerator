# -*- coding: utf-8 -*-
"""
Streamlit app for Email Assistant with live agent trace.
Shows only the currently executing agent's output.
"""

import os
import tempfile
import streamlit as st
import openai
import time

from memory.json_memory import get_profile, upsert_profile
from workflow.langgraph_flow import run_email_workflow
from agents.input_parser_agent import InputParserAgent
from agents.intent_detection_agent import IntentDetectionAgent
from agents.tone_stylist_agent import ToneStylistAgent
from agents.draft_writer_agent import DraftWriterAgent
from agents.personalization_agent import PersonalizationAgent
from agents.review_agent import ReviewAgent
from agents.router_agent import RouterAgent
from integrations.llm_client import make_openai_llm



def main():
    st.set_page_config(page_title="AI Powered Email Generator", layout="wide")
    st.title("AI Powered Email Generator")

    tabs = st.tabs(["Profile", "Compose & Draft"])

    # Profile Tab
    with tabs[0]:
        st.header("User Profile")
        profile = get_profile("default")
        with st.form("profile_form", clear_on_submit=False):
            name = st.text_input("Sender name", value=profile.get("name", "SP"), help="Name used in email signature.")
            company = st.text_input("Company", value=profile.get("company", "True Startup"), help="Your company name.")
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
                st.success("Profile saved.")

    # Compose & Draft Tab
    with tabs[1]:
        st.header("Compose & Draft")
        left, right = st.columns([2, 3])

        with left:
            st.subheader("Compose Email")
            mode = st.radio("Input mode", ["Text", "Voice"], index=0, help="Choose text or voice input.")
            user_text = ""
            if mode == "Text":
                user_text = st.text_area(
                    "Describe your email intent",
                    height=200,
                    help="Provide details for your email."
                )
            else:
                st.info("Upload an audio file (WAV, MP3, M4A, MP4).")
                if "voice_text" not in st.session_state:
                    st.session_state["voice_text"] = ""
                audio_file = st.file_uploader("Upload audio", type=["wav", "mp3", "m4a", "mp4"])
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
                    st.session_state["voice_text"] = getattr(transcript, "text", "")
                    st.write("Transcription:")
                    st.write(st.session_state["voice_text"])
                user_text = st.session_state["voice_text"]

            tone_choice = st.selectbox("Tone (optional)", ["(profile)", "formal", "casual", "assertive"], index=0, help="Select the tone for your email.")

            if st.button("Generate Email Draft"):
                if not user_text:
                    st.warning("Please enter text or upload voice input.")
                else:
                    extra = f"\n\ntone: {tone_choice}" if tone_choice != "(profile)" else ""
                    full_text = user_text + extra

                    with st.spinner("Generating email draft..."):
                        result = run_email_workflow(full_text)

                    # Save result for right panel
                    st.session_state["last_result"] = result
                    st.success("Email draft generated!")

                    # ===========================
                    # Agent Traces Section
                    # ===========================
                    st.subheader("Agent Execution Trace")

                    traces = result.get("traces", [])

                    if not traces:
                        st.info("No trace data available.")
                    else:
                        for trace in traces:
                            with st.expander(
                                f"{trace['agent']} • {trace['duration_ms']} ms",
                                expanded=False
                            ):
                                st.markdown(f"**Agent:** {trace['agent']}")
                                st.markdown(f"**Duration:** {trace['duration_ms']} ms")
                                st.markdown(f"**Timestamp:** {trace['timestamp']}")
                                st.markdown("**Input Keys:**")
                                st.code(", ".join(trace.get("input_keys", [])))
                                st.markdown("**Output Keys:**")
                                st.code(", ".join(trace.get("output_keys", [])))


        with right:
            st.subheader("Draft & Actions")
            last = st.session_state.get("last_result")
            if last:
                draft = last.get("personalized_draft") or last.get("draft") or {}
                subject = draft.get("subject", "")
                body = draft.get("body", "")
            else:
                subject = ""
                body = ""
                st.info("No email generated yet.")
            subject_edit = st.text_input("Subject", subject, help="Edit the subject before exporting or saving.")
            body_edit = st.text_area("Body", body, height=400, help="Edit the body before exporting or saving.")
            st.download_button(
                "Export as .txt",
                data=f"Subject: {subject_edit}\n\n{body_edit}",
                file_name="email_draft.txt",
                mime="text/plain",
                disabled=not bool(subject_edit or body_edit),
            )
            if st.button("Save to Profile History", disabled=not last):
                prof = get_profile("default")
                prof.setdefault("sent_examples", []).append({"subject": subject_edit, "body": body_edit})
                upsert_profile("default", prof)
                st.success("Draft saved to profile history.")

if __name__ == "__main__":
    main()
