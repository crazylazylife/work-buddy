---
name: security_redactor
description: Redact likely secrets, private keys, emails, and sensitive numbers before external-facing drafts.
---

# Security Redactor

## When To Use
Use this skill whenever source text may be stored, summarized, or drafted into Jira, Slack, email, or GitHub output.

## Redaction Targets
- API keys.
- Tokens.
- Passwords.
- Private keys.
- Email addresses.
- Long sensitive numeric identifiers.

## Tool Flow
Use tools backed by `ledger.redact_sensitive`; ingestion and draft tools apply redaction before storage or external-facing payloads.

## Safety Rules
- Redaction is a guardrail, not a guarantee.
- If content appears highly sensitive, ask whether it should be summarized instead of copied.
- Never include raw credentials in PR bodies, Slack drafts, email drafts, or Jira drafts.
