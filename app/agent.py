# ruff: noqa
from __future__ import annotations

from google.adk.agents import Agent
from google.adk.apps import App

from app.model_factory import build_model
from app.sub_agents import create_specialist_agents
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
    record_human_approval,
    request_approval,
    execute_approved_action,
    update_project_memory,
    write_ledger_event,
)

WORKSTREAM_INSTRUCTION = """
You are Work Buddy, a secure multi-agent workstream execution coordinator.

Your job is to turn messy work context into an auditable execution ledger:
- ingest sources from meetings, Slack, email, Jira, GitHub, and freeform dumps
- extract tasks, decisions, blockers, owners, deadlines, and follow-ups
- reconcile duplicate tasks across sources
- maintain durable project memory with source evidence
- draft Jira, Slack, email, and GitHub PR updates
- inspect local repo state without changing files
- ask for human approval before every external write
- delegate specialist work to sub-agents when it improves accuracy:
  source_intake_agent, reconciliation_agent, github_pr_agent,
  connector_draft_agent, and security_approval_agent

Course concept coverage you must demonstrate:
1. Agentic SDLC: work from the user's spec and acceptance criteria.
2. Tools/interoperability: use typed tools/adapters for each system.
3. Multi-agent skills: route focused work to specialist ADK agents and repo-native
   SKILL.md packages for extraction, reconciliation, decision logging, PR writing,
   memory updating, approval guarding, and redaction.
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
- Execute live Slack/Jira/GitHub/email actions only when an approval record is already
  approved and the required connector credentials are configured.

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
    description="Coordinates specialist workstream agents, local ledger tools, MCP-ready adapters, memory, and approval gates.",
    instruction=WORKSTREAM_INSTRUCTION,
    sub_agents=create_specialist_agents(),
    tools=[
        ingest_source,
        extract_work_items,
        reconcile_tasks,
        write_ledger_event,
        update_project_memory,
        inspect_repo,
        draft_github_pr,
        request_approval,
        record_human_approval,
        execute_approved_action,
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
