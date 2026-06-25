# Work Buddy: Workstream Control Agent

Work Buddy is an ADK-based agent that turns messy project context into an auditable execution ledger. It coordinates meeting transcripts, Slack/email/Jira-style dumps, local repo state, and GitHub PR workflows without pretending that a summary is the same thing as execution.

The core artifact is a local ledger that answers:

- What was requested?
- Where did the request come from?
- What tasks, decisions, blockers, and deadlines were extracted?
- What changed locally?
- What PR/Jira/Slack/email drafts were prepared?
- What still needs human approval?
- What source evidence supports each status update?

## What It Does

- Ingests meeting transcripts, Slack exports, email text, Jira issue text, GitHub context, and freeform work dumps.
- Extracts tasks, decisions, blockers, owners, deadlines, dependencies, and follow-ups.
- Reconciles duplicate tasks across multiple sources.
- Maintains durable local memory and append-only audit events.
- Drafts Jira updates, Slack replies, email replies, GitHub PR titles, PR bodies, branch names, and commit messages.
- Creates approval records before any external write.
- Inspects local Git repo status and recent commits without mutating the repo.
- Redacts likely secrets, tokens, private keys, emails, and sensitive numbers before preparing external-facing drafts.

## What It Does Not Do Yet

- It does not connect to live Jira, Slack, Gmail, or GitHub APIs in v1.
- It does not send messages, update tickets, push branches, open PRs, or merge PRs.
- It does not mark work as done/merged/shipped/deployed unless tool evidence exists.

Those live integrations are intentionally v2 work. The capstone MVP focuses on safe agentic coordination, inspectable memory, approvals, and evaluation.

## Course Concept Coverage

- **Day 1: Agentic SDLC + vibe coding** - behavior is captured in `.agents-cli-spec.md`, then implemented as an ADK prototype.
- **Day 2: Tools + interoperability** - each external system is modeled as a typed adapter/tool; mocks can later become MCP servers or live API connectors.
- **Day 3: Skills** - the agent instruction routes through focused capabilities: extraction, reconciliation, decision logging, PR writing, memory updating, approval guarding, and redaction.
- **Day 4: Security + evaluation** - external writes are approval-gated, evidence is preserved, and evals check safety-sensitive behavior.
- **Day 5: Production-grade development** - scaffolded with Agents CLI, includes a spec, tests, eval cases, and a deployment path.

## Architecture

```text
User / ADK Playground
        |
        v
Workstream Control Agent
        |
        +-- Source ingestion tools
        +-- Task / decision / blocker extraction
        +-- Cross-source reconciliation
        +-- Local memory updater
        +-- Mock Jira / Slack / email adapters
        +-- Local repo inspector
        +-- GitHub PR draft generator
        +-- Human approval gate
        |
        v
Local execution ledger
```

Key files:

- `.agents-cli-spec.md` - product/spec source of truth.
- `app/agent.py` - ADK agent definition, model selection, instructions, tool wiring.
- `app/tools.py` - typed agent tools and mock adapters.
- `app/ledger.py` - local ledger, task reconciliation, memory, PR drafts, approvals, redaction.
- `tests/unit/test_ledger.py` - deterministic business-logic tests.
- `tests/eval/datasets/basic-dataset.json` - capstone eval prompts.
- `tests/eval/eval_config.yaml` - quality, evidence, and approval-gate eval metrics.

## Ledger Layout

When the agent runs tools, it writes inspectable files under `ledger/`:

```text
ledger/
  inbox/       raw normalized sources
  tasks/       canonical task records
  decisions/   future decision records
  changes/     future local change summaries
  prs/         GitHub-ready PR drafts
  approvals/   pending human approval records
  memory/      durable project memory
  events/      append-only audit events
```

The ledger is local by default so a capstone reviewer can inspect exactly what the agent did.

## Permissions Model

The v1 policy is conservative:

- Local ledger and memory updates are allowed.
- Drafting Jira, Slack, email, and GitHub artifacts is allowed.
- Posting Slack, sending email, updating Jira, pushing branches, opening PRs, merging PRs, or marking external work complete requires a `request_approval` record.
- The agent must cite source evidence for task and status changes when available.
- The agent must record conflicts instead of silently choosing between inconsistent facts.

## Model Support

Default model backend:

- Gemini via Google ADK/Vertex using `gemini-flash-latest`.

Additional supported backends:

- OpenAI models through ADK's `LiteLlm` wrapper.
- Anthropic Claude models through `LiteLlm`.
- Local/open-source models through Ollama or vLLM using OpenAI-compatible tool-calling endpoints.
- Other LiteLLM-supported providers.

ADK documents this model flexibility in its official model docs: [AI Models for ADK agents](https://adk.dev/agents/models/) and [LiteLLM integration](https://adk.dev/agents/models/litellm/).

### Gemini / Vertex

```powershell
$env:WORKSTREAM_MODEL_PROVIDER = "gemini"
$env:WORKSTREAM_MODEL = "gemini-flash-latest"
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
agents-cli playground
```

### OpenAI

```powershell
$env:WORKSTREAM_MODEL_PROVIDER = "openai"
$env:WORKSTREAM_MODEL = "gpt-4o-mini"
$env:OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
agents-cli playground
```

The code maps that to `openai/gpt-4o-mini` for LiteLLM.

### Claude

```powershell
$env:WORKSTREAM_MODEL_PROVIDER = "claude"
$env:WORKSTREAM_MODEL = "claude-3-5-sonnet-latest"
$env:ANTHROPIC_API_KEY = "YOUR_ANTHROPIC_API_KEY"
agents-cli playground
```

The code maps that to `anthropic/claude-3-5-sonnet-latest` for LiteLLM.

### Ollama / Local Open-Source

Start Ollama separately, then run:

```powershell
$env:WORKSTREAM_MODEL_PROVIDER = "ollama"
$env:WORKSTREAM_MODEL = "llama3.1"
$env:PYTHONUTF8 = "1"
agents-cli playground
```

The code maps that to `ollama_chat/llama3.1` for LiteLLM. For reliable agent tools, choose a local model/server that supports tool/function calling.

### vLLM or OpenAI-Compatible Endpoint

```powershell
$env:WORKSTREAM_MODEL_PROVIDER = "litellm"
$env:WORKSTREAM_MODEL = "openai/my-served-model"
$env:OPENAI_API_BASE = "https://your-vllm-endpoint.example.com/v1"
$env:OPENAI_API_KEY = "YOUR_ENDPOINT_KEY"
agents-cli playground
```

## Setup

Install prerequisites:

- Python 3.11+
- `uv`
- `agents-cli`
- Google Cloud SDK if using Gemini/Vertex

Install dependencies:

```powershell
agents-cli install
```

Run deterministic tests:

```powershell
uv run pytest tests\unit tests\integration\test_agent.py
```

Run lint:

```powershell
uv run --extra lint ruff check .
```

Launch the ADK playground:

```powershell
agents-cli playground
```

## Demo Flow

Prompt 1:

```text
Ingest this meeting transcript, extract work items, reconcile tasks, and update memory.

Maya: Please update the onboarding email by Friday.
Liam: Decision: we will keep the current approval workflow.
Priya: Blocked waiting on security review.
```

Expected result:

- A `ledger/inbox/SRC-*.json` source file.
- A `ledger/tasks/TASK-*.json` task file.
- A `ledger/events/EVT-*.json` audit event.
- A memory update in `ledger/memory/project-context.md`.

Prompt 2:

```text
Draft a GitHub PR body for TASK-001. Do not open a live PR.
```

Expected result:

- A PR draft in `ledger/prs/`.
- No live GitHub PR is opened.

Prompt 3:

```text
Post this Slack update to #release: The approval workflow is done and merged.
```

Expected result:

- The agent drafts the Slack update.
- The agent creates a pending approval in `ledger/approvals/`.
- The agent should not claim the work is merged without evidence.

## Evaluation

The project includes eval prompts and custom metrics for:

- task extraction from noisy context
- approval gates for external writes
- source evidence preservation
- memory update behavior
- PR drafting behavior

After configuring model credentials:

```powershell
agents-cli eval run
```

## Production Path

Keep v1 local for the capstone MVP. Add deployment after tests and evals pass:

- Use **Agent Runtime** if OAuth/user-consent connectors become central.
- Use **Cloud Run** if Slack webhooks, scheduled digests, or background sync become central.
- Store live API credentials in Secret Manager, not local files.
- Keep prompt-response logging metadata-only unless sensitive-data policy allows content logging.

## Roadmap

- Live Jira API connector.
- Live Slack OAuth app and message posting after approval.
- Gmail/Google Workspace ingestion and send-after-approval.
- GitHub branch/PR creation after approval.
- MCP servers for connector portability.
- Scheduled workstream digest on Cloud Run.
- Cloud SQL or managed memory backend for multi-user production use.
