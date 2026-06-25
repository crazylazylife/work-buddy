from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEDGER_ROOT = Path(os.environ.get("WORKSTREAM_LEDGER_DIR", "ledger"))

SOURCE_TYPES = {
    "meeting",
    "slack",
    "email",
    "jira",
    "github",
    "freeform",
    "transcript",
}

EXTERNAL_WRITE_ACTIONS = {
    "post_slack_message",
    "send_email",
    "update_jira",
    "push_branch",
    "open_github_pr",
    "mark_external_complete",
    "merge_pr",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_ledger() -> None:
    for name in [
        "inbox",
        "tasks",
        "decisions",
        "changes",
        "prs",
        "approvals",
        "memory",
        "events",
    ]:
        (LEDGER_ROOT / name).mkdir(parents=True, exist_ok=True)

    memory_file = LEDGER_ROOT / "memory" / "project-context.md"
    if not memory_file.exists():
        memory_file.write_text(
            "# Project Context\n\n"
            "This memory is updated by Workstream Control Agent from sourced work events.\n",
            encoding="utf-8",
        )


def next_id(prefix: str, folder: str, suffix: str) -> str:
    ensure_ledger()
    existing = sorted((LEDGER_ROOT / folder).glob(f"{prefix}-*.{suffix}"))
    if not existing:
        return f"{prefix}-001"
    last = existing[-1].stem.split("-")[-1]
    return f"{prefix}-{int(last) + 1:03d}"


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def parse_metadata(metadata_json: str | None) -> dict[str, Any]:
    if not metadata_json:
        return {}
    try:
        value = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {"raw_metadata": metadata_json}
    return value if isinstance(value, dict) else {"metadata": value}


def redact_sensitive(text: str) -> str:
    patterns = [
        (r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[\w\-./+=]{8,}", r"\1=[REDACTED]"),
        (r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
        (r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[REDACTED_EMAIL]"),
        (r"\b(?:\d[ -]*?){13,16}\b", "[REDACTED_NUMBER]"),
    ]
    redacted = text
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted, flags=re.DOTALL | re.IGNORECASE)
    return redacted


def append_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    event_id = next_id("EVT", "events", "json")
    event = {
        "id": event_id,
        "event_type": event_type,
        "created_at": utc_now(),
        "payload": payload,
    }
    write_json(LEDGER_ROOT / "events" / f"{event_id}.json", event)
    return event


def store_source(
    content: str,
    source_type: str = "freeform",
    metadata_json: str | None = None,
) -> dict[str, Any]:
    ensure_ledger()
    normalized_type = source_type.lower().strip()
    if normalized_type not in SOURCE_TYPES:
        normalized_type = "freeform"

    source_id = next_id("SRC", "inbox", "json")
    redacted_content = redact_sensitive(content)
    source = {
        "id": source_id,
        "source_type": normalized_type,
        "received_at": utc_now(),
        "metadata": parse_metadata(metadata_json),
        "content": redacted_content,
        "redactions_applied": redacted_content != content,
        "confidence": "source_provided",
    }
    write_json(LEDGER_ROOT / "inbox" / f"{source_id}.json", source)
    append_event("source_ingested", {"source_id": source_id, "source_type": normalized_type})
    return source


def load_source(source_id: str) -> dict[str, Any]:
    source = read_json(LEDGER_ROOT / "inbox" / f"{source_id}.json")
    if not source:
        raise ValueError(f"Unknown source_id: {source_id}")
    return source


def infer_owner(line: str) -> str | None:
    speaker_match = re.match(r"\s*([A-Z][A-Za-z ._-]{1,40})\s*:", line)
    if speaker_match:
        return speaker_match.group(1).strip()
    at_match = re.search(r"@([A-Za-z][\w.-]+)", line)
    if at_match:
        return at_match.group(1)
    owner_match = re.search(r"(?i)\b(owner|assigned to|by)\s+([A-Z][A-Za-z ._-]{1,40})", line)
    if owner_match:
        return owner_match.group(2).strip()
    return None


def infer_deadline(line: str) -> str | None:
    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", line)
    if date_match:
        return date_match.group(0)
    relative_match = re.search(
        r"(?i)\b(today|tomorrow|by friday|by monday|by eod|next week|this week|end of week)\b",
        line,
    )
    if relative_match:
        return relative_match.group(0)
    return None


def summarize_line(line: str) -> str:
    cleaned = re.sub(r"^\s*[-*]\s*", "", line).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:180]


def extract_candidates(source_id: str) -> dict[str, Any]:
    source = load_source(source_id)
    tasks: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    task_pattern = re.compile(
        r"(?i)\b(todo|action|follow up|follow-up|need to|needs to|must|should|please|implement|update|fix|draft|create|prepare|ship|send)\b"
    )
    decision_pattern = re.compile(r"(?i)\b(decided|decision|we will|agreed|chosen|approved)\b")
    blocker_pattern = re.compile(r"(?i)\b(blocked|blocker|waiting on|risk|dependency|depends on|unclear|conflict)\b")

    for index, raw_line in enumerate(source["content"].splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        evidence = {
            "source_id": source_id,
            "source_type": source["source_type"],
            "line": index,
            "quote": summarize_line(line),
        }
        is_blocker = bool(blocker_pattern.search(line))
        if task_pattern.search(line) and not is_blocker:
            tasks.append(
                {
                    "summary": summarize_line(line),
                    "owner": infer_owner(line) or "unknown",
                    "deadline": infer_deadline(line) or "unknown",
                    "status": "candidate",
                    "source_evidence": [evidence],
                    "confidence": "medium",
                }
            )
        if decision_pattern.search(line):
            decisions.append(
                {
                    "decision": summarize_line(line),
                    "source_evidence": [evidence],
                    "confidence": "medium",
                }
            )
        if is_blocker:
            blockers.append(
                {
                    "summary": summarize_line(line),
                    "source_evidence": [evidence],
                    "confidence": "medium",
                }
            )

    return {
        "source_id": source_id,
        "tasks": tasks,
        "decisions": decisions,
        "blockers": blockers,
        "counts": {
            "tasks": len(tasks),
            "decisions": len(decisions),
            "blockers": len(blockers),
        },
    }


def task_key(summary: str) -> set[str]:
    stop = {"the", "and", "for", "with", "that", "this", "from", "task", "todo", "need", "needs", "please"}
    return {word for word in re.findall(r"[a-z0-9]+", summary.lower()) if len(word) > 3 and word not in stop}


def load_tasks() -> list[dict[str, Any]]:
    ensure_ledger()
    tasks: list[dict[str, Any]] = []
    for path in sorted((LEDGER_ROOT / "tasks").glob("TASK-*.json")):
        tasks.append(read_json(path, {}))
    return tasks


def save_task(task: dict[str, Any]) -> None:
    write_json(LEDGER_ROOT / "tasks" / f"{task['id']}.json", task)


def reconcile_candidate_tasks(candidates_json: str) -> dict[str, Any]:
    try:
        payload = json.loads(candidates_json)
    except json.JSONDecodeError as exc:
        raise ValueError("candidates_json must be valid JSON") from exc

    candidates = payload.get("tasks", payload if isinstance(payload, list) else [])
    if not isinstance(candidates, list):
        raise ValueError("candidates_json must contain a task list")

    existing = load_tasks()
    created: list[str] = []
    updated: list[str] = []

    for candidate in candidates:
        summary = str(candidate.get("summary", "")).strip()
        if not summary:
            continue
        candidate_key = task_key(summary)
        match = None
        for task in existing:
            overlap = candidate_key & task_key(task.get("summary", ""))
            if candidate_key and len(overlap) >= max(2, min(4, len(candidate_key))):
                match = task
                break

        if match:
            match.setdefault("source_evidence", []).extend(candidate.get("source_evidence", []))
            match.setdefault("history", []).append(
                {
                    "at": utc_now(),
                    "event": "reconciled_duplicate_candidate",
                    "candidate_summary": summary,
                }
            )
            if match.get("deadline") != candidate.get("deadline") and candidate.get("deadline") not in {None, "unknown"}:
                match.setdefault("conflicts", []).append(
                    {
                        "field": "deadline",
                        "existing": match.get("deadline"),
                        "incoming": candidate.get("deadline"),
                        "at": utc_now(),
                    }
                )
            save_task(match)
            updated.append(match["id"])
        else:
            task_id = next_id("TASK", "tasks", "json")
            task = {
                "id": task_id,
                "summary": summary,
                "status": "open",
                "owner": candidate.get("owner", "unknown"),
                "deadline": candidate.get("deadline", "unknown"),
                "priority": "normal",
                "source_evidence": candidate.get("source_evidence", []),
                "linked_jira": None,
                "linked_github": None,
                "dependencies": [],
                "blockers": [],
                "actions_taken": [],
                "approval_required": [],
                "conflicts": [],
                "history": [{"at": utc_now(), "event": "created_from_candidate"}],
            }
            save_task(task)
            existing.append(task)
            created.append(task_id)

    append_event("tasks_reconciled", {"created": created, "updated": updated})
    return {"created": created, "updated": updated, "task_count": len(load_tasks())}


def update_memory(note: str, source_id: str | None = None) -> dict[str, Any]:
    ensure_ledger()
    memory_file = LEDGER_ROOT / "memory" / "project-context.md"
    entry = f"\n\n## {utc_now()}\n"
    if source_id:
        entry += f"Source: {source_id}\n\n"
    entry += redact_sensitive(note).strip() + "\n"
    with memory_file.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    event = append_event("memory_updated", {"source_id": source_id, "note": redact_sensitive(note)})
    return {"memory_file": str(memory_file), "event_id": event["id"]}


def create_approval(action_type: str, target_system: str, payload_json: str, risk_level: str = "medium") -> dict[str, Any]:
    if action_type not in EXTERNAL_WRITE_ACTIONS:
        risk_level = "low" if risk_level == "medium" else risk_level
    approval_id = next_id("APR", "approvals", "json")
    payload = parse_metadata(payload_json)
    approval = {
        "id": approval_id,
        "action_type": action_type,
        "target_system": target_system,
        "risk_level": risk_level,
        "status": "pending_human_approval",
        "created_at": utc_now(),
        "payload_preview": payload,
        "execution_result": None,
        "policy": "External writes require explicit human approval before execution.",
    }
    write_json(LEDGER_ROOT / "approvals" / f"{approval_id}.json", approval)
    append_event("approval_requested", {"approval_id": approval_id, "action_type": action_type})
    return approval


def draft_pr(task_id: str, repo_path: str = ".") -> dict[str, Any]:
    task = read_json(LEDGER_ROOT / "tasks" / f"{task_id}.json")
    if not task:
        raise ValueError(f"Unknown task_id: {task_id}")

    slug = "-".join(re.findall(r"[a-z0-9]+", task["summary"].lower())[:6]) or task_id.lower()
    branch = f"workstream/{task_id.lower()}-{slug}"
    title = f"{task_id}: {task['summary'][:68]}"
    body = (
        f"## Summary\n"
        f"- {task['summary']}\n\n"
        f"## Source Evidence\n"
        + "\n".join(f"- {item.get('source_id')} line {item.get('line')}: {item.get('quote')}" for item in task.get("source_evidence", []))
        + "\n\n## Test Plan\n- Run unit tests for ledger extraction and approval gates.\n- Run agent evals for task extraction, reconciliation, safety, and PR drafting.\n\n"
        "## Approval\nThis PR draft was prepared locally and must be reviewed before creating a live GitHub PR.\n"
    )
    pr_id = next_id("PR", "prs", "json")
    draft = {
        "id": pr_id,
        "task_id": task_id,
        "repo_path": repo_path,
        "branch_name": branch,
        "commit_message": f"{task_id}: {task['summary'][:60]}",
        "title": title,
        "body": redact_sensitive(body),
        "status": "draft_requires_approval",
        "created_at": utc_now(),
    }
    write_json(LEDGER_ROOT / "prs" / f"{pr_id}.json", draft)
    if not isinstance(task.get("linked_github"), dict):
        task["linked_github"] = {}
    task["linked_github"]["draft_pr"] = pr_id
    task.setdefault("actions_taken", []).append({"at": utc_now(), "action": "drafted_pr", "pr_id": pr_id})
    save_task(task)
    append_event("github_pr_drafted", {"task_id": task_id, "pr_id": pr_id})
    return draft


def inspect_git_repo(repo_path: str = ".") -> dict[str, Any]:
    path = Path(repo_path).resolve()
    if not path.exists():
        return {"ok": False, "error": f"Path does not exist: {path}"}

    def run_git(args: list[str]) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=path,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return result.stderr.strip() or result.stdout.strip()
        return result.stdout.strip()

    return {
        "ok": True,
        "repo_path": str(path),
        "status": run_git(["status", "--short"]),
        "branch": run_git(["branch", "--show-current"]),
        "recent_commits": run_git(["log", "--oneline", "-5"]),
    }
