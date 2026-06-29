from __future__ import annotations

import json

from app import ledger
from app.live_connectors import execute_approved_action as execute_live_approved_action


def ingest_source(content: str, source_type: str = "freeform", metadata_json: str = "{}") -> dict:
    """Store a workstream source in the local execution ledger.

    Args:
        content: Meeting transcript, Slack/email/Jira text, GitHub context, or freeform work dump.
        source_type: One of meeting, slack, email, jira, github, transcript, or freeform.
        metadata_json: Optional JSON object with source_ref, participants, links, or visibility.

    Returns:
        The normalized source record with its ledger id.
    """
    return ledger.store_source(content=content, source_type=source_type, metadata_json=metadata_json)


def extract_work_items(source_id: str) -> dict:
    """Extract candidate tasks, decisions, and blockers from a stored source."""
    return ledger.extract_candidates(source_id)


def reconcile_tasks(candidates_json: str) -> dict:
    """Merge candidate tasks into canonical ledger tasks.

    Args:
        candidates_json: JSON from extract_work_items, or a JSON array of task candidates.

    Returns:
        Created and updated task ids.
    """
    return ledger.reconcile_candidate_tasks(candidates_json)


def write_ledger_event(event_type: str, payload_json: str = "{}") -> dict:
    """Append an auditable event to the ledger."""
    return ledger.append_event(event_type, ledger.parse_metadata(payload_json))


def update_project_memory(note: str, source_id: str = "") -> dict:
    """Append durable project memory with optional source evidence."""
    return ledger.update_memory(note, source_id or None)


def inspect_repo(repo_path: str = ".") -> dict:
    """Inspect a local Git repository without changing files."""
    return ledger.inspect_git_repo(repo_path)


def draft_github_pr(task_id: str, repo_path: str = ".") -> dict:
    """Create a GitHub-ready PR draft for a tracked task without opening a live PR."""
    return ledger.draft_pr(task_id, repo_path)


def request_approval(action_type: str, target_system: str, payload_json: str, risk_level: str = "medium") -> dict:
    """Create a human approval request for an external write or risky status update."""
    return ledger.create_approval(action_type, target_system, payload_json, risk_level)


def record_human_approval(approval_id: str, decision: str, approved_by: str, human_confirmation: str) -> dict:
    """Record a human approval or rejection decision.

    Args:
        approval_id: The approval id to update.
        decision: Either approved or rejected.
        approved_by: Human reviewer identifier.
        human_confirmation: Must be exactly 'I approve this external action' for approvals.

    Returns:
        Updated approval record.
    """
    return ledger.record_approval_decision(approval_id, decision, approved_by, human_confirmation)


def execute_approved_action(approval_id: str) -> dict:
    """Execute a live external action only after its approval record is approved."""
    return execute_live_approved_action(approval_id)


def mock_jira_search(query: str) -> dict:
    """Search mocked Jira issues for capstone demos."""
    sample_issues = [
        {"key": "WCA-12", "summary": "Create execution ledger for workstream sources", "status": "In Progress"},
        {"key": "WCA-21", "summary": "Draft GitHub PR body from task evidence", "status": "To Do"},
        {"key": "WCA-34", "summary": "Add approval gate before external writes", "status": "Review"},
    ]
    matches = [issue for issue in sample_issues if query.lower() in issue["summary"].lower() or query.lower() in issue["key"].lower()]
    return {"query": query, "matches": matches or sample_issues[:2], "mode": "mock"}


def mock_jira_update_draft(issue_key: str, update_text: str) -> dict:
    """Draft a Jira update and create an approval request instead of writing to Jira."""
    payload = {"issue_key": issue_key, "update_text": ledger.redact_sensitive(update_text)}
    approval = ledger.create_approval("update_jira", "jira", json.dumps(payload), "medium")
    return {"draft": payload, "approval": approval, "external_write_executed": False}


def mock_slack_thread_ingest(thread_text: str, channel: str = "demo-channel") -> dict:
    """Ingest a mocked Slack thread into the ledger."""
    return ledger.store_source(thread_text, "slack", json.dumps({"channel": channel, "mode": "mock"}))


def mock_slack_reply_draft(channel: str, message: str) -> dict:
    """Draft a Slack reply and create an approval request instead of posting."""
    payload = {"channel": channel, "message": ledger.redact_sensitive(message)}
    approval = ledger.create_approval("post_slack_message", "slack", json.dumps(payload), "medium")
    return {"draft": payload, "approval": approval, "external_write_executed": False}


def mock_email_ingest(email_text: str, mailbox_label: str = "demo") -> dict:
    """Ingest a mocked email into the ledger."""
    return ledger.store_source(email_text, "email", json.dumps({"mailbox_label": mailbox_label, "mode": "mock"}))


def mock_email_reply_draft(recipient: str, subject: str, body: str) -> dict:
    """Draft an email reply and create an approval request instead of sending."""
    payload = {
        "recipient": ledger.redact_sensitive(recipient),
        "subject": subject,
        "body": ledger.redact_sensitive(body),
    }
    approval = ledger.create_approval("send_email", "email", json.dumps(payload), "high")
    return {"draft": payload, "approval": approval, "external_write_executed": False}
