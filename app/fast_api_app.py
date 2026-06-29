import json
import os
from pathlib import Path
from typing import Any

import google.auth
from fastapi import Body, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging

from app import ledger
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback
from app.live_connectors import require_env
from app.tools import (
    draft_github_pr,
    execute_approved_action,
    extract_work_items,
    ingest_source,
    inspect_repo,
    mock_email_reply_draft,
    mock_jira_search,
    mock_jira_update_draft,
    mock_slack_reply_draft,
    reconcile_tasks,
    record_human_approval,
    request_approval,
    update_project_memory,
)

REQUIRED_BODY = Body(...)


class LocalLogger:
    def log_struct(self, payload: dict[str, Any], severity: str = "INFO") -> None:
        print({"severity": severity, "payload": payload})


setup_telemetry()
try:
    _, project_id = google.auth.default()
    logging_client = google_cloud_logging.Client()
    logger = logging_client.logger(__name__)
    otel_to_cloud = True
except Exception:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "local-dev-project")
    logger = LocalLogger()
    otel_to_cloud = False

allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")
AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = Path(__file__).parent / "static"
session_service_uri = None
artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifact_service_uri,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=otel_to_cloud,
)
app.title = "Work Buddy"
app.description = "ADK multi-agent workstream control API and dashboard"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/ui", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/ledger")
def ledger_summary() -> dict[str, Any]:
    ledger.ensure_ledger()
    return {
        "tasks": ledger.load_tasks(),
        "approvals": [
            ledger.read_json(path, {})
            for path in sorted((ledger.LEDGER_ROOT / "approvals").glob("APR-*.json"))
        ],
        "prs": [
            ledger.read_json(path, {})
            for path in sorted((ledger.LEDGER_ROOT / "prs").glob("PR-*.json"))
        ],
        "events": [
            ledger.read_json(path, {})
            for path in sorted((ledger.LEDGER_ROOT / "events").glob("EVT-*.json"))
        ][-25:],
        "memory": (ledger.LEDGER_ROOT / "memory" / "project-context.md").read_text(
            encoding="utf-8"
        )
        if (ledger.LEDGER_ROOT / "memory" / "project-context.md").exists()
        else "",
    }


@app.get("/api/connectors")
def connector_status() -> dict[str, Any]:
    checks = {
        "slack": require_env("SLACK_BOT_TOKEN"),
        "jira": require_env("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"),
        "github": require_env("GITHUB_TOKEN", "GITHUB_REPOSITORY"),
        "smtp": require_env("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"),
    }
    return {
        name: {"configured": ok, **({} if ok else details)}
        for name, (ok, details) in checks.items()
    }


@app.post("/api/ingest")
def api_ingest(payload: dict[str, Any] = REQUIRED_BODY) -> dict[str, Any]:
    source = ingest_source(
        content=payload.get("content", ""),
        source_type=payload.get("source_type", "freeform"),
        metadata_json=payload.get("metadata_json", "{}"),
    )
    extraction = extract_work_items(source["id"])
    reconciliation = reconcile_tasks(json.dumps(extraction))
    memory = update_project_memory(
        f"Processed {source['source_type']} source {source['id']} with "
        f"{extraction['counts']['tasks']} task(s), "
        f"{extraction['counts']['decisions']} decision(s), and "
        f"{extraction['counts']['blockers']} blocker(s).",
        source["id"],
    )
    return {
        "source": source,
        "extraction": extraction,
        "reconciliation": reconciliation,
        "memory": memory,
    }


@app.post("/api/pr-drafts")
def api_pr_draft(payload: dict[str, Any] = REQUIRED_BODY) -> dict[str, Any]:
    return draft_github_pr(
        task_id=payload.get("task_id", ""),
        repo_path=payload.get("repo_path", "."),
    )


@app.post("/api/drafts/slack")
def api_slack_draft(payload: dict[str, Any] = REQUIRED_BODY) -> dict[str, Any]:
    return mock_slack_reply_draft(
        channel=payload.get("channel", ""),
        message=payload.get("message", ""),
    )


@app.post("/api/drafts/jira")
def api_jira_draft(payload: dict[str, Any] = REQUIRED_BODY) -> dict[str, Any]:
    return mock_jira_update_draft(
        issue_key=payload.get("issue_key", ""),
        update_text=payload.get("update_text", ""),
    )


@app.post("/api/drafts/email")
def api_email_draft(payload: dict[str, Any] = REQUIRED_BODY) -> dict[str, Any]:
    return mock_email_reply_draft(
        recipient=payload.get("recipient", ""),
        subject=payload.get("subject", ""),
        body=payload.get("body", ""),
    )


@app.post("/api/approvals/request")
def api_request_approval(payload: dict[str, Any] = REQUIRED_BODY) -> dict[str, Any]:
    return request_approval(
        action_type=payload.get("action_type", ""),
        target_system=payload.get("target_system", ""),
        payload_json=payload.get("payload_json", "{}"),
        risk_level=payload.get("risk_level", "medium"),
    )


@app.post("/api/approvals/{approval_id}/decision")
def api_approval_decision(
    approval_id: str, payload: dict[str, Any] = REQUIRED_BODY
) -> dict[str, Any]:
    return record_human_approval(
        approval_id=approval_id,
        decision=payload.get("decision", ""),
        approved_by=payload.get("approved_by", "ui-user"),
        human_confirmation=payload.get("human_confirmation", ""),
    )


@app.post("/api/approvals/{approval_id}/execute")
def api_execute_approval(approval_id: str) -> dict[str, Any]:
    return execute_approved_action(approval_id)


@app.get("/api/jira/search")
def api_jira_search(query: str) -> dict[str, Any]:
    return mock_jira_search(query)


@app.get("/api/repo")
def api_repo(repo_path: str = ".") -> dict[str, Any]:
    return inspect_repo(repo_path)


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
