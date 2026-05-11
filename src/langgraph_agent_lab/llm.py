from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv


def build_openai_client(enabled: bool = True) -> Any | None:
    if not enabled:
        return None

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required when OpenAI integration is enabled")

    from openai import OpenAI

    return OpenAI(api_key=api_key)


def configured_openai_model(default: str = "gpt-4.1-mini") -> str:
    load_dotenv()
    return os.getenv("OPENAI_MODEL", default)
