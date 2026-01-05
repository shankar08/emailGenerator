import json
from src.integrations.llm_client import make_openai_llm
from src.workflow.langgraph_flow import run_email_workflow

llm = make_openai_llm(model="gpt-4o", temperature=0)

def validate_scores(scores: dict) -> bool:
    required_keys = [
        "intent_accuracy",
        "tone_alignment",
        "clarity",
        "professionalism",
        "completeness",
        "grammar",
        "overall_score",
    ]

    for key in required_keys:
        val = scores.get(key)
        if not isinstance(val, int) or not (1 <= val <= 10):
            return False
    return True


def judge_email(user_input: str, tone: str, subject: str, body: str):
    llm = make_openai_llm(model="gpt-4o", temperature=0)

    prompt = f"""
            You are an expert email reviewer.

            IMPORTANT:
            - Scores MUST be integers from 1 to 10 ONLY.
            - Do NOT use decimals.
            - Do NOT exceed 10.
            - Do NOT change the keys.

            USER REQUEST:
            {user_input}

            REQUESTED TONE:
            {tone}

            GENERATED EMAIL:
            Subject: {subject}

            {body}

            Return ONLY valid JSON with EXACTLY these keys:
            - intent_accuracy (1-10)
            - tone_alignment (1-10)
            - clarity (1-10)
            - professionalism (1-10)
            - completeness (1-10)
            - grammar (1-10)
            - overall_score (1-10)
            - explanation
            """

    response = llm.invoke(prompt)

    try:
        scores = json.loads(response.content)
    except Exception:
        return {
            "error": "Failed to parse JSON from judge",
            "raw_output": response.content
        }

    if not validate_scores(scores):
        return {
            "error": "Invalid score scale (expected integers 110)",
            "raw_output": scores
        }

    return scores

def run_eval():
    dataset = json.load(open("eval/email_eval_set.json"))
    results = []

    for example in dataset:
        result = run_email_workflow(example["input"])
        draft = result.get("personalized_draft", {})
        email_text = f"{draft.get('subject','')}\n\n{draft.get('body','')}"

        score = judge_email(
            example["input"],
            example["tone"],
            email_text
        )

        results.append({
            "id": example["id"],
            "scores": score
        })

if __name__ == "__main__":
    run_eval()