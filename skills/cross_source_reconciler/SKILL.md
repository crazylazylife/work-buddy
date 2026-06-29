---
name: cross_source_reconciler
description: Merge duplicate task candidates across sources while preserving evidence and recording conflicts.
---

# Cross-Source Reconciler

## When To Use
Use this skill after extraction, or when the same task appears in a meeting, Slack thread, email, Jira issue, or GitHub context.

## Inputs
- JSON from `extract_work_items`.
- Existing ledger task records.

## Tool Flow
1. Call `reconcile_tasks` with the candidate JSON.
2. Call `write_ledger_event` for notable conflicts or reconciliation decisions.
3. Call `update_project_memory` with an evidence-backed summary.

## Safety Rules
- Never delete prior source evidence.
- Record deadline/status conflicts instead of silently choosing one.
- Do not mark a task done, shipped, merged, or deployed unless a tool result proves it.
