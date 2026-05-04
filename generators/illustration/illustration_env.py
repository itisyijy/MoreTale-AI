import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def resolve_api_key() -> str:
    key = (os.getenv("NANO_BANANA_KEY") or "").strip()
    if key:
        return key
    raise ValueError("NANO_BANANA_KEY environment variable not set.")
