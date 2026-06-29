---
name: github_pr_writer
description: Draft GitHub branch names, commit messages, PR titles, PR bodies, changelogs, and test plans from tracked task evidence.
---

# GitHub PR Writer

## When To Use
Use this skill when a tracked task needs a GitHub-ready implementation or review package.

## Inputs
- Task id.
- Optional local repository path.

## Tool Flow
1. Call `inspect_repo` to gather non-mutating local Git context.
2. Call `draft_github_pr` with the task id.
3. If the user asks to open, push, merge, or update a live GitHub PR, call `request_approval`.

## Safety Rules
- Do not push branches, open live PRs, merge PRs, or edit remote GitHub state without approval.
- Link PR content to task id and source evidence.
- Include test plan and approval note in the PR body.
