---
name: decision_logger
description: Capture decisions, rationale, options considered, and source evidence in the workstream ledger.
---

# Decision Logger

## When To Use
Use this skill when source text contains phrases such as `decision`, `decided`, `agreed`, `approved`, `we will`, or when the user asks why a change happened.

## Inputs
- Decision text.
- Source id and evidence line if available.
- Optional rationale, alternatives, owner, or date.

## Tool Flow
1. Use extracted decision candidates from `extract_work_items`.
2. Call `write_ledger_event` for important decisions.
3. Call `update_project_memory` with the decision and evidence.

## Safety Rules
- Preserve original wording as evidence.
- If rationale is missing, state that it is missing.
- Do not infer approval authority unless explicitly present in source evidence.
