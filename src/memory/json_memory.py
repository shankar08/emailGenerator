"""
json_memory.py

JSON-backed memory store for user profiles and past drafts.
Automatically syncs updates to GitHub.
"""
import json
from pathlib import Path
from typing import Dict, Any
import streamlit as st

try:
    from github import Github
except ImportError:
    raise ImportError(
        "PyGithub is required for GitHub sync. Install via: pip install PyGithub"
    )

# -----------------------------
# Local JSON path
# -----------------------------
MEMORY_PATH = Path(__file__).parent / "user_profiles.json"

# -----------------------------
# GitHub config (via Streamlit secrets)
# -----------------------------
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
REPO_NAME = st.secrets.get("GITHUB_REPO")
FILE_PATH_IN_REPO = "src/memory/user_profiles.json"

# -----------------------------
# Local JSON helpers
# -----------------------------
def load_profiles() -> Dict[str, Any]:
    if not MEMORY_PATH.exists():
        return {}
    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_profiles(data: Dict[str, Any]) -> None:
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_profile(user_id: str = "default") -> Dict[str, Any]:
    data = load_profiles()
    return data.get(user_id, {})

# -----------------------------
# GitHub sync
# -----------------------------
def push_to_github(data: Dict[str, Any]) -> None:
    if not GITHUB_TOKEN or not REPO_NAME:
        print("GitHub token or repo not set. Skipping GitHub sync.")
        return

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)

    # Try to update the existing file
    try:
        contents = repo.get_contents(FILE_PATH_IN_REPO)
        repo.update_file(
            path=FILE_PATH_IN_REPO,
            message="Update user_profiles.json",
            content=json.dumps(data, indent=2, ensure_ascii=False),
            sha=contents.sha
        )
    except Exception:
        # If file doesn't exist, create it
        repo.create_file(
            path=FILE_PATH_IN_REPO,
            message="Create user_profiles.json",
            content=json.dumps(data, indent=2, ensure_ascii=False)
        )

# -----------------------------
# Upsert profile
# -----------------------------
def upsert_profile(user_id: str, profile: Dict[str, Any]) -> None:
    data = load_profiles()
    data[user_id] = profile
    save_profiles(data)        # update local JSON
    push_to_github(data)       # sync to GitHub
