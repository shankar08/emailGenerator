import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List

EVAL_STORE_PATH = "memory/eval_history.json"


def _load_all() -> List[Dict[str, Any]]:
    if not os.path.exists(EVAL_STORE_PATH):
        return []

    try:
        with open(EVAL_STORE_PATH, "r") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except json.JSONDecodeError:
        # Corrupted or partially-written file
        return []


def _save_all(records: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(EVAL_STORE_PATH), exist_ok=True)

    tmp_path = EVAL_STORE_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(records, f, indent=2)

    os.replace(tmp_path, EVAL_STORE_PATH)


def save_eval(
    prompt: str,
    draft: Dict[str, Any],
    scores: Dict[str, Any],
) -> str:
    records = _load_all()

    eval_id = str(uuid.uuid4())

    record = {
        "eval_id": eval_id,
        "timestamp": datetime.utcnow().isoformat(),
        "prompt": prompt,
        "subject": draft.get("subject", ""),
        "body": draft.get("body", ""),
        "scores": scores,
    }

    records.append(record)
    _save_all(records)

    return eval_id


def get_eval_history(limit: int = 50) -> List[Dict[str, Any]]:
    records = _load_all()
    return sorted(records, key=lambda r: r["timestamp"], reverse=True)[:limit]