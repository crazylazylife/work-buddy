from __future__ import annotations

from google.adk.agents import Agent

from app.model_factory import build_model
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


def create_source_intake_agent() -> Agent:
    return Agent(
        name="source_intake_agent",
        model=build_model(),
        description="Ingests workstream sources and extracts tasks, decisions, blockers, owners, and deadlines.",
        instruction=(
            "You are the source intake specialist. Use ingestion tools for meeting, Slack, email, "
            "Jira, GitHub, and freeform dumps. After ingestion, call extract_work_items and return "
            "the source id, extracted candidates, and any ambiguity that needs clarification."
        ),
        tools=[
            ingest_source,
            mock_slack_thread_ingest,
            mock_email_ingest,
            extract_work_items,
        ],
    )


def create_reconciliation_agent() -> Agent:
    return Agent(
        name="reconciliation_agent",
        model=build_model(),
        description="Reconciles extracted candidates into canonical tasks and durable project memory.",
        instruction=(
            "You are the reconciliation specialist. Merge duplicate task candidates, preserve source "
            "evidence, record conflicts instead of choosing silently, write audit events, and update "
            "project memory with concise evidence-backed summaries."
        ),
        tools=[
            reconcile_tasks,
            write_ledger_event,
            update_project_memory,
        ],
    )


def create_github_agent() -> Agent:
    return Agent(
        name="github_pr_agent",
        model=build_model(),
        description="Inspects local repository state and drafts GitHub PR artifacts from tracked tasks.",
        instruction=(
            "You are the GitHub PR specialist. Inspect local repo state without changing files. Draft "
            "branch names, commit messages, PR titles, and PR bodies linked to task evidence. Never "
            "open live PRs or push branches; create an approval request for live GitHub actions."
        ),
        tools=[
            inspect_repo,
            draft_github_pr,
            request_approval,
        ],
    )


def create_connector_agent() -> Agent:
    return Agent(
        name="connector_draft_agent",
        model=build_model(),
        description="Drafts Jira, Slack, and email updates through mock adapters and approval gates.",
        instruction=(
            "You are the connector drafting specialist. Search mocked Jira context and draft Jira, "
            "Slack, or email updates. Every external write must return a pending approval record and "
            "must not be executed directly."
        ),
        tools=[
            mock_jira_search,
            mock_jira_update_draft,
            mock_slack_reply_draft,
            mock_email_reply_draft,
            request_approval,
            record_human_approval,
            execute_approved_action,
        ],
    )


def create_security_agent() -> Agent:
    return Agent(
        name="security_approval_agent",
        model=build_model(),
        description="Applies security policy, redaction expectations, and human-in-the-loop approval rules.",
        instruction=(
            "You are the security and approval specialist. Check whether requested actions are local, "
            "draft-only, or external writes. External writes require request_approval. Never let the "
            "system claim done, shipped, deployed, or merged without tool evidence."
        ),
        tools=[
            request_approval,
            record_human_approval,
            execute_approved_action,
            write_ledger_event,
        ],
    )


def create_specialist_agents() -> list[Agent]:
    return [
        create_source_intake_agent(),
        create_reconciliation_agent(),
        create_github_agent(),
        create_connector_agent(),
        create_security_agent(),
    ]
