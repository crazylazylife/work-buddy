from __future__ import annotations

import base64
import json
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any

from app import ledger


def require_env(*names: str) -> tuple[bool, dict[str, str]]:
    values = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        return False, {"missing": ", ".join(missing)}
    return True, values


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return {"ok": 200 <= response.status < 300, "status": response.status, "body": body}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "body": exc.read().decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def put_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return {"ok": 200 <= response.status < 300, "status": response.status, "body": body}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "body": exc.read().decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def execute_slack(payload: dict[str, Any]) -> dict[str, Any]:
    ok, env = require_env("SLACK_BOT_TOKEN")
    if not ok:
        return {"ok": False, "mode": "not_configured", **env}
    return post_json(
        "https://slack.com/api/chat.postMessage",
        {"channel": payload["channel"], "text": payload["message"]},
        {"Authorization": f"Bearer {env['SLACK_BOT_TOKEN']}"},
    )


def execute_jira(payload: dict[str, Any]) -> dict[str, Any]:
    ok, env = require_env("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
    if not ok:
        return {"ok": False, "mode": "not_configured", **env}
    token = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
    issue_key = payload["issue_key"]
    return put_json(
        f"{env['JIRA_BASE_URL'].rstrip('/')}/rest/api/3/issue/{issue_key}",
        {"fields": {"description": payload["update_text"]}},
        {"Authorization": f"Basic {token}", "Accept": "application/json"},
    )


def execute_github_pr(payload: dict[str, Any]) -> dict[str, Any]:
    ok, env = require_env("GITHUB_TOKEN", "GITHUB_REPOSITORY")
    if not ok:
        return {"ok": False, "mode": "not_configured", **env}
    return post_json(
        f"https://api.github.com/repos/{env['GITHUB_REPOSITORY']}/pulls",
        {
            "title": payload["title"],
            "body": payload["body"],
            "head": payload["head"],
            "base": payload.get("base", "main"),
        },
        {
            "Authorization": f"Bearer {env['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def execute_email(payload: dict[str, Any]) -> dict[str, Any]:
    ok, env = require_env("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
    if not ok:
        return {"ok": False, "mode": "not_configured", **env}

    message = EmailMessage()
    message["From"] = env["SMTP_FROM"]
    message["To"] = payload["recipient"]
    message["Subject"] = payload["subject"]
    message.set_content(payload["body"])

    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(env["SMTP_HOST"], port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(env["SMTP_USERNAME"], env["SMTP_PASSWORD"])
            smtp.send_message(message)
        return {"ok": True, "mode": "smtp_sent"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def execute_approved_action(approval_id: str) -> dict[str, Any]:
    approval = ledger.load_approval(approval_id)
    if approval["status"] != "approved":
        return {
            "ok": False,
            "approval_id": approval_id,
            "status": approval["status"],
            "reason": "approval must be explicitly approved before execution",
        }

    payload = approval.get("payload_preview") or {}
    action_type = approval["action_type"]
    if action_type == "post_slack_message":
        result = execute_slack(payload)
    elif action_type == "update_jira":
        result = execute_jira(payload)
    elif action_type == "open_github_pr":
        result = execute_github_pr(payload)
    elif action_type == "send_email":
        result = execute_email(payload)
    else:
        result = {"ok": False, "reason": f"No live connector for action_type: {action_type}"}

    return ledger.record_approval_execution(approval_id, result)
