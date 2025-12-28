
import json
from typing import Dict, Any
from pathlib import Path
from langsmith import traceable

# Load tone samples
TONE_SAMPLES_PATH = Path(__file__).parent.parent.parent / "data" / "tone_samples.json"
with open(TONE_SAMPLES_PATH, "r", encoding="utf-8") as f:
    TONE_SAMPLES = json.load(f)

class ToneStylistAgent:
    @staticmethod
    @traceable(run_type="llm")
    def run(state: Dict[str, Any]) -> Dict[str, Any]:
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
