---
name: approval_guard
description: Enforce human-in-the-loop approval before external writes or risky status changes.
---

# Approval Guard

## When To Use
Use this skill before any action that could affect external systems, other people, or official project status.

## External Writes
- Slack post.
- Email send.
- Jira update.
- GitHub branch push.
- GitHub PR creation.
- PR merge.
- External status change to done, shipped, deployed, or merged.

## Tool Flow
1. Draft the intended action.
2. Call `request_approval` with `action_type`, `target_system`, `payload_json`, and `risk_level`.
3. Return the approval id and make clear that no external write was executed.
4. Only after explicit human approval is recorded may `execute_approved_action` attempt a live connector call.

## Safety Rules
- Approval is required even if the user phrases the request as an imperative.
- Do not execute an external write unless the approval record is approved and required credentials are configured.
- Do not claim completion without evidence.
