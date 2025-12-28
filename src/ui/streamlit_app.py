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

    # -------------------------
    # Top Navbar: User Profile
    # -------------------------
    profile = get_profile("default")
    with st.form("profile_form", clear_on_submit=False):
        nav1, nav2, nav3, nav4 = st.columns([2, 2, 3, 2])
        with nav1:
            st.markdown("#### User Profile")
        with nav2:
            name = st.text_input("Sender name", value=profile.get("name", "SP"), key="name_input")
        with nav3:
            company = st.text_input("Company", value=profile.get("company", "True Startup"), key="company_input")
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

    # -------------------------
    # Main layout
    # -------------------------
    col1, col2 = st.columns([2, 3])

    with col1:
        st.subheader("Compose")
        mode = st.radio("Input mode", ["Text", "Voice"], index=0)
        user_text = ""

        if mode == "Text":
            user_text = st.text_area(
                "Describe intent (e.g., 'to: Alice\\nFollow-up on meeting... tone: formal')",
                height=200,
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

        tone_choice = st.selectbox("Tone (optional)", ["(profile)", "formal", "casual", "assertive"], index=0)

        if st.button("Generate email"):
            if not user_text:
                st.warning("Enter text or upload voice input.")
            else:
                extra = f"\n\ntone: {tone_choice}" if tone_choice != "(profile)" else ""
                full_text = user_text + extra

                # -------------------------
                # Placeholders
                # -------------------------
                spinner_placeholder = st.empty()
                spinner_placeholder.info("Generating draft...")
                trace_placeholder = st.empty()

                # Initialize state
                state = {"messages": [{"content": full_text}], "flow": []}


                llm = make_openai_llm()

                agents = [
                    ("input_parser_agent", lambda s: InputParserAgent.run(s)),
                    ("intent_detection_agent", lambda s: IntentDetectionAgent.run(s, llm)),
                    ("tone_stylist_agent", lambda s: ToneStylistAgent.run(s)),
                    ("draft_writer_agent", lambda s: DraftWriterAgent.run(s, llm)),
                    ("personalization_agent", lambda s: PersonalizationAgent.run(s)),
                    ("review_agent", lambda s: ReviewAgent.run(s, llm)),
                    ("router_agent", lambda s: RouterAgent.run(s)),
                ]

                for i, (name, fn) in enumerate(agents):
                    output = fn(state)
                    state.update(output)
                    state["flow"].append({"agent": name, "output": output})

                    # Show only the currently executing agent
                    trace_placeholder.markdown(f"### {name}")
                    trace_placeholder.json(output)

                # Hide spinner when the last agent finishes
                spinner_placeholder.empty()
                st.session_state["last_result"] = state
                st.success("Email draft generation complete.")
    # -------------------------
    # Draft & Actions Column
    # -------------------------
    with col2:
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

        subject_edit = st.text_input("Subject", subject)
        # body_edit = st.text_area("Body", body, height=400)
        body_placeholder = st.empty()
        streamed_body = ""
        for char in body:
            streamed_body += char
            body_placeholder.text_area("Body", streamed_body, height=400)
            time.sleep(0.01)  # Adjust speed as needed

        body_edit = streamed_body

        st.download_button(
            "Download .txt",
            data=f"Subject: {subject_edit}\n\n{body_edit}",
            file_name="email_draft.txt",
            mime="text/plain",
            disabled=not bool(subject_edit or body_edit),
        )

        if st.button("Save to profile history", disabled=not last):
            prof = get_profile("default")
            prof.setdefault("sent_examples", []).append({"subject": subject_edit, "body": body_edit})
            upsert_profile("default", prof)
            st.success("Saved.")

        if st.button("Simulate send", disabled=not last):
            prof = get_profile("default")
            prof.setdefault("sent_examples", []).append({"subject": subject_edit, "body": body_edit})
            upsert_profile("default", prof)
            st.success("Email sent (simulation).")

    st.markdown("---")
    st.markdown("~ True AI power for composing email.😄")

if __name__ == "__main__":
    main()
