---
name: meeting_task_extractor
description: Extract tasks, decisions, blockers, owners, deadlines, dependencies, and follow-ups from meeting transcripts or freeform work dumps.
---

# Meeting Task Extractor

## When To Use
Use this skill when a user provides a meeting transcript, Slack thread, email, Jira text, GitHub context, or freeform dump and asks what work needs to be tracked.

## Inputs
- Raw source text.
- Source type: `meeting`, `slack`, `email`, `jira`, `github`, `transcript`, or `freeform`.
- Optional metadata JSON with participants, source reference, links, or visibility.

## Tool Flow
1. Call `ingest_source`.
2. Call `extract_work_items` with the returned source id.
3. Return extracted tasks, decisions, blockers, owners, deadlines, and ambiguity.

## Safety Rules
- Preserve source evidence for every extracted item.
- Redact secrets and personal identifiers through the ledger tools.
- Do not invent owners or deadlines; use `unknown` and ask for clarification.
