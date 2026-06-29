from __future__ import annotations

import os

import google.auth
from google.adk.models import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

try:
    _, project_id = google.auth.default()
except Exception:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "local-dev-project")

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")


def build_model() -> Gemini | LiteLlm:
    """Build the configured model backend.

    Default: Gemini through ADK/Vertex.
    Alternative: LiteLLM for OpenAI, Anthropic Claude, Ollama, vLLM, and other
    OpenAI-compatible or open-source model hosts.
    """
    provider = os.environ.get("WORKSTREAM_MODEL_PROVIDER", "gemini").strip().lower()
    model_name = os.environ.get("WORKSTREAM_MODEL", "gemini-flash-latest").strip()

    if provider in {"litellm", "openai", "anthropic", "claude", "ollama", "vllm"}:
        if provider == "openai" and "/" not in model_name:
            model_name = f"openai/{model_name}"
        elif provider in {"anthropic", "claude"} and "/" not in model_name:
            model_name = f"anthropic/{model_name}"
        elif provider == "ollama" and "/" not in model_name:
            model_name = f"ollama_chat/{model_name}"
        return LiteLlm(model=model_name)

    return Gemini(
        model=model_name,
        retry_options=types.HttpRetryOptions(attempts=3),
    )
