# -*- coding: utf-8 -*-
"""
store.py

Unified JSON-backed persistence for:
- User profiles
- Evaluation history

Features:
- Safe JSON loading
- Atomic writes
- Optional GitHub sync (profiles + evals)
"""

import json
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

import streamlit as st

# =============================
# Paths
# =============================
BASE_DIR = Path(__file__).parent

PROFILE_PATH = BASE_DIR / "user_profiles.json"
EVAL_PATH = BASE_DIR / "eval_history.json"

# =============================
# GitHub Sync Config
# =============================
try:
    from github import Github
except ImportError:
    Github = None

GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
REPO_NAME = st.secrets.get("GITHUB_REPO")

PROFILE_REPO_PATH = "src/memory/user_profiles.json"
EVAL_REPO_PATH = "src/memory/eval_history.json"

# =============================
# Generic JSON helpers
# =============================
def _safe_load(path: Path, default):
    if not path.exists():
        return default

    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return default
        return json.loads(content)
    except json.JSONDecodeError:
        return default


def _atomic_save(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    os.replace(tmp, path)


# =============================
# GitHub Sync Helpers
# =============================
def _push_to_github(repo_path: str, data: Any, commit_message: str):
    if not Github or not GITHUB_TOKEN or not REPO_NAME:
        return

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        content = json.dumps(data, indent=2, ensure_ascii=False)

        try:
            existing = repo.get_contents(repo_path)
            repo.update_file(
                path=repo_path,
                message=commit_message,
                content=content,
                sha=existing.sha,
            )
        except Exception:
            repo.create_file(
                path=repo_path,
                message=f"Create {repo_path}",
                content=content,
            )
    except Exception as e:
        # Never crash the app because of GitHub
        print(f"[GitHub Sync Error] {repo_path}: {e}")


# =============================
# Profile Store
# =============================
def load_profiles() -> Dict[str, Any]:
    return _safe_load(PROFILE_PATH, {})


def save_profiles(data: Dict[str, Any]) -> None:
    _atomic_save(PROFILE_PATH, data)
    _push_to_github(
        PROFILE_REPO_PATH,
        data,
        "Update user_profiles.json",
    )


def get_profile(user_id: str = "default") -> Dict[str, Any]:
    return load_profiles().get(user_id, {})


def upsert_profile(user_id: str, profile: Dict[str, Any]) -> None:
    data = load_profiles()
    data[user_id] = profile
    save_profiles(data)


# =============================
# Eval Store
# =============================
def _load_evals() -> List[Dict[str, Any]]:
    return _safe_load(EVAL_PATH, [])


def _save_evals(records: List[Dict[str, Any]]) -> None:
    _atomic_save(EVAL_PATH, records)
    _push_to_github(
        EVAL_REPO_PATH,
        records,
        "Update eval_history.json",
    )


def save_eval(
    prompt: str,
    draft: Dict[str, Any],
    scores: Dict[str, Any],
) -> str:
    records = _load_evals()

    eval_id = str(uuid.uuid4())

    records.append(
        {
            "eval_id": eval_id,
            "timestamp": datetime.utcnow().isoformat(),
            "prompt": prompt,
            "subject": draft.get("subject", ""),
            "body": draft.get("body", ""),
            "scores": scores,
        }
    )

    _save_evals(records)
    return eval_id


def get_eval_history(limit: int = 50) -> List[Dict[str, Any]]:
    records = _load_evals()
    return sorted(records, key=lambda r: r["timestamp"], reverse=True)[:limit]