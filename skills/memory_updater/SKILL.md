---
name: memory_updater
description: Maintain durable project memory and append-only event history as new workstream information arrives.
---

# Memory Updater

## When To Use
Use this skill after ingestion, reconciliation, approvals, PR drafts, or any user-provided correction.

## Inputs
- Memory note.
- Optional source id.

## Tool Flow
1. Call `update_project_memory`.
2. Call `write_ledger_event` when the memory update is tied to an action, conflict, approval, or correction.

## Safety Rules
- Append memory; do not overwrite history.
- Mark stale/disputed facts instead of deleting them.
- Include source ids whenever available.
