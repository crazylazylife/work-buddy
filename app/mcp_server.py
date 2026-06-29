from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

from app.tools import (
    draft_github_pr,
    execute_approved_action,
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
    record_human_approval,
    request_approval,
    update_project_memory,
    write_ledger_event,
)

ToolFn = Callable[..., dict]

TOOLS: dict[str, tuple[ToolFn, str, dict[str, Any]]] = {
    "ingest_source": (
        ingest_source,
        "Store a workstream source in the local execution ledger.",
        {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "source_type": {"type": "string"},
                "metadata_json": {"type": "string"},
            },
            "required": ["content"],
        },
    ),
    "extract_work_items": (
        extract_work_items,
        "Extract candidate tasks, decisions, and blockers from a source id.",
        {"type": "object", "properties": {"source_id": {"type": "string"}}, "required": ["source_id"]},
    ),
    "reconcile_tasks": (
        reconcile_tasks,
        "Merge candidate tasks into canonical ledger tasks.",
        {"type": "object", "properties": {"candidates_json": {"type": "string"}}, "required": ["candidates_json"]},
    ),
    "write_ledger_event": (
        write_ledger_event,
        "Append an auditable event to the ledger.",
        {
            "type": "object",
            "properties": {"event_type": {"type": "string"}, "payload_json": {"type": "string"}},
            "required": ["event_type"],
        },
    ),
    "update_project_memory": (
        update_project_memory,
        "Append durable project memory with optional source evidence.",
        {
            "type": "object",
            "properties": {"note": {"type": "string"}, "source_id": {"type": "string"}},
            "required": ["note"],
        },
    ),
    "inspect_repo": (
        inspect_repo,
        "Inspect a local Git repository without changing files.",
        {"type": "object", "properties": {"repo_path": {"type": "string"}}},
    ),
    "draft_github_pr": (
        draft_github_pr,
        "Create a GitHub-ready PR draft for a tracked task without opening a live PR.",
        {
            "type": "object",
            "properties": {"task_id": {"type": "string"}, "repo_path": {"type": "string"}},
            "required": ["task_id"],
        },
    ),
    "request_approval": (
        request_approval,
        "Create a pending human approval request for an external write.",
        {
            "type": "object",
            "properties": {
                "action_type": {"type": "string"},
                "target_system": {"type": "string"},
                "payload_json": {"type": "string"},
                "risk_level": {"type": "string"},
            },
            "required": ["action_type", "target_system", "payload_json"],
        },
    ),
    "record_human_approval": (
        record_human_approval,
        "Record an explicit human approval or rejection decision.",
        {
            "type": "object",
            "properties": {
                "approval_id": {"type": "string"},
                "decision": {"type": "string"},
                "approved_by": {"type": "string"},
                "human_confirmation": {"type": "string"},
            },
            "required": ["approval_id", "decision", "approved_by", "human_confirmation"],
        },
    ),
    "execute_approved_action": (
        execute_approved_action,
        "Execute a configured live external connector only after approval is approved.",
        {
            "type": "object",
            "properties": {"approval_id": {"type": "string"}},
            "required": ["approval_id"],
        },
    ),
    "mock_jira_search": (
        mock_jira_search,
        "Search mocked Jira issues for capstone demos.",
        {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    ),
    "mock_jira_update_draft": (
        mock_jira_update_draft,
        "Draft a Jira update and create an approval request instead of writing.",
        {
            "type": "object",
            "properties": {"issue_key": {"type": "string"}, "update_text": {"type": "string"}},
            "required": ["issue_key", "update_text"],
        },
    ),
    "mock_slack_thread_ingest": (
        mock_slack_thread_ingest,
        "Ingest a mocked Slack thread into the ledger.",
        {
            "type": "object",
            "properties": {"thread_text": {"type": "string"}, "channel": {"type": "string"}},
            "required": ["thread_text"],
        },
    ),
    "mock_slack_reply_draft": (
        mock_slack_reply_draft,
        "Draft a Slack reply and create an approval request instead of posting.",
        {
            "type": "object",
            "properties": {"channel": {"type": "string"}, "message": {"type": "string"}},
            "required": ["channel", "message"],
        },
    ),
    "mock_email_ingest": (
        mock_email_ingest,
        "Ingest a mocked email into the ledger.",
        {
            "type": "object",
            "properties": {"email_text": {"type": "string"}, "mailbox_label": {"type": "string"}},
            "required": ["email_text"],
        },
    ),
    "mock_email_reply_draft": (
        mock_email_reply_draft,
        "Draft an email reply and create an approval request instead of sending.",
        {
            "type": "object",
            "properties": {
                "recipient": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["recipient", "subject", "body"],
        },
    ),
}


def make_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def tool_descriptions() -> list[dict[str, Any]]:
    return [
        {"name": name, "description": description, "inputSchema": schema}
        for name, (_, description, schema) in TOOLS.items()
    ]


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}

    if method == "initialize":
        return make_result(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "work-buddy-ledger-mcp", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return make_result(request_id, {"tools": tool_descriptions()})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            return make_error(request_id, -32602, f"Unknown tool: {name}")
        try:
            result = TOOLS[name][0](**arguments)
        except Exception as exc:
            return make_error(request_id, -32000, str(exc))
        return make_result(
            request_id,
            {"content": [{"type": "text", "text": json.dumps(result, indent=2, sort_keys=True)}]},
        )
    return make_error(request_id, -32601, f"Unsupported method: {method}")


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
        except Exception as exc:
            response = make_error(None, -32700, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
