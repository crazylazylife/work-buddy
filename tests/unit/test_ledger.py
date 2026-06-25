import json

from app import ledger


def test_ingest_extract_reconcile_updates_ledger(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ledger, "LEDGER_ROOT", tmp_path / "ledger")

    source = ledger.store_source(
        "Maya: Please update the checkout copy by Friday.\n"
        "Decision: we will keep the old payment provider.\n"
        "Blocked waiting on Legal review.",
        "meeting",
        "{}",
    )
    candidates = ledger.extract_candidates(source["id"])
    result = ledger.reconcile_candidate_tasks(json.dumps(candidates))

    assert candidates["counts"]["tasks"] == 1
    assert candidates["counts"]["decisions"] == 1
    assert candidates["counts"]["blockers"] == 1
    assert result["created"] == ["TASK-001"]

    task = ledger.read_json(tmp_path / "ledger" / "tasks" / "TASK-001.json")
    assert task["owner"] == "Maya"
    assert task["deadline"].lower() == "by friday"
    assert task["source_evidence"][0]["source_id"] == source["id"]


def test_external_write_creates_pending_approval(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ledger, "LEDGER_ROOT", tmp_path / "ledger")

    approval = ledger.create_approval(
        "send_email",
        "email",
        '{"recipient": "person@example.com", "body": "token=abc123456789"}',
        "high",
    )

    assert approval["status"] == "pending_human_approval"
    assert approval["target_system"] == "email"
    assert approval["payload_preview"]["recipient"] == "person@example.com"


def test_draft_pr_links_back_to_task(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ledger, "LEDGER_ROOT", tmp_path / "ledger")
    source = ledger.store_source("Action: create approval gate before Slack posts.", "freeform", "{}")
    candidates = ledger.extract_candidates(source["id"])
    ledger.reconcile_candidate_tasks(json.dumps(candidates))

    draft = ledger.draft_pr("TASK-001", ".")
    task = ledger.read_json(tmp_path / "ledger" / "tasks" / "TASK-001.json")

    assert draft["status"] == "draft_requires_approval"
    assert draft["task_id"] == "TASK-001"
    assert task["linked_github"]["draft_pr"] == draft["id"]
