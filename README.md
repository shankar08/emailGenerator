# Agentic AI Email Generator

## 1. Introduction

The Agentic AI Email Generator is a smart assistant designed to help professionals quickly draft, personalize, and review emails. Leveraging a multi-agent workflow and advanced language models, it produces high-quality, context-aware email drafts tailored to your needs in seconds.

---

## 2. Features

- **Rapid Email Drafting:** Compose emails in under 2 minutes.
- **Context Awareness:** Adapts content and tone based on your input and recipient.
- **Multiple Tones:** Choose from formal, casual, or assertive styles.
- **Versatile Use Cases:** Supports outreach, follow-ups, internal updates, and more.
- **Personalization & Memory:** Remembers your preferences and previous drafts.
- **Voice Input:** Dictate your intent for hands-free drafting.
- **Grammar & Tone Review:** Built-in review agent for clarity and correctness.

---

## 3. How It Works

The app uses a modular, multi-agent system to process your input and generate polished emails:

1. **Input Parser:** Extracts intent, recipient, tone, and constraints from your prompt.
2. **Intent Detector:** Classifies your email (outreach, follow-up, apology, etc.).
3. **Tone Stylist:** Adjusts language style to your selected tone.
4. **Draft Writer:** Generates the main email body.
5. **Personalization Agent:** Inserts your name, signature, and context.
6. **Review Agent:** Checks grammar, tone, and coherence.
7. **Router Agent:** Handles fallback logic and memory updates.

---

## 4. Usage

1. Launch the app (locally or on Streamlit Cloud).
2. Select your desired **email tone** (formal, casual, assertive).
3. Enter or speak your **email intent**.
4. Preview, edit, and export your personalized draft.
5. Optionally, save drafts to your profile history.

---

## 5. Architecture

The application is organized as follows:

```text
Email-Generator/
├── streamlit_app.py               # Streamlit Cloud entrypoint (thin UI bootstrap)
├── requirements.txt               # Python dependencies
├── README.md                      # Architecture, setup, and usage details
│
├── src/
│   ├── ui/
│   │   └── streamlit_app.py       # UI components, forms, preview, export
│   ├── agents/
│   │   ├── draft_writer_agent.py
│   │   ├── input_parser_agent.py
│   │   ├── intent_decision_agent.py
│   │   ├── personalization_agent.py
│   │   ├── review_agent.py
│   │   ├── router_agent.py
│   │   └── tone_stylist_agent.py
│   ├── example_voice_inputs/
│   │   ├── assertive.m4a
│   │   ├── friendly.m4a
│   │   └── professional.m4a
│   ├── workflow/
│   │   └── langgraph_flow.py      # LangGraph StateGraph orchestration
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── json_memory.py
│   │   └── user_profiles.json
│   ├── integrations/
│   │   └── llm_client.py          # OpenAI LLM
│   └── runtime.txt                # Python version
├── data/
│   └── tone_samples.json
```

---

## Example Voice Intents

Sample voice input files are available in `src/example_voice_inputs/`.

---

## Deployment

**Streamlit Cloud:** https://appapppy-tp7ghummmwsicrrwbvraws.streamlit.app

```

```
