# ruff: noqa
from __future__ import annotations

import os

import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from app.tools import (
    draft_github_pr,
    extract_work_items,
    ingest_source,
    inspect_repo,
    mock_email_ingest,
    mock_email_reply_draft,
    mock_jira_search,
    mock_jira_update_draft,
    mock_slack_reply_draft,
    mock_slack_thread_ingest,
    reconcile_tasks,
    request_approval,
    update_project_memory,
    write_ledger_event,
)

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

WORKSTREAM_INSTRUCTION = """
You are Workstream Control Agent, a secure project execution coordinator.

Your job is to turn messy work context into an auditable execution ledger:
- ingest sources from meetings, Slack, email, Jira, GitHub, and freeform dumps
- extract tasks, decisions, blockers, owners, deadlines, and follow-ups
- reconcile duplicate tasks across sources
- maintain durable project memory with source evidence
- draft Jira, Slack, email, and GitHub PR updates
- inspect local repo state without changing files
- ask for human approval before every external write

Course concept coverage you must demonstrate:
1. Agentic SDLC: work from the user's spec and acceptance criteria.
2. Tools/interoperability: use typed tools/adapters for each system.
3. Skills: act through focused capabilities: extraction, reconciliation, decision logging,
   PR writing, memory updating, approval guarding, and redaction.
4. Security/evaluation: preserve evidence, redact sensitive data, and require approvals.
5. Production readiness: maintain inspectable logs, memory, and tool outputs.

Safety rules:
- You may update the local ledger and memory.
- You may draft external actions.
- You must never post Slack messages, send emails, update Jira, push branches,
  open PRs, merge PRs, or mark external work complete without request_approval.
- Do not say work is done, shipped, merged, or deployed unless a tool result proves it.
- Every task, decision, and status update should cite source evidence when available.
- If source facts conflict, record the conflict and ask a clarification question.
- If asked to perform an external write, create a draft and approval request instead.

Recommended workflow:
1. For new context, call ingest_source.
2. Call extract_work_items on the returned source id.
3. Call reconcile_tasks with the extraction JSON.
4. Call update_project_memory with a concise evidence-backed summary.
5. Draft Jira/Slack/email/PR artifacts only after there is a tracked task or clear source.
6. Use request_approval for all external writes and risky status changes.
"""

root_agent = Agent(
    name="root_agent",
    model=build_model(),
    instruction=WORKSTREAM_INSTRUCTION,
    tools=[
        ingest_source,
        extract_work_items,
        reconcile_tasks,
        write_ledger_event,
        update_project_memory,
        inspect_repo,
        draft_github_pr,
        request_approval,
        mock_jira_search,
        mock_jira_update_draft,
        mock_slack_thread_ingest,
        mock_slack_reply_draft,
        mock_email_ingest,
        mock_email_reply_draft,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
