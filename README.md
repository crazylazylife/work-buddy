# Work Buddy: Workstream Control Agent

Work Buddy is an ADK-based multi-agent system that turns messy project context into an auditable execution ledger. It coordinates meeting transcripts, Slack/email/Jira-style dumps, local repo state, and GitHub PR workflows without pretending that a summary is the same thing as execution.

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

- Live Jira, Slack, SMTP email, and GitHub PR execution are optional and credential-gated.
- It does not push branches or merge PRs.
- It does not mark work as done/merged/shipped/deployed unless tool evidence exists.

The default capstone path still uses mocks/drafts. Live connector execution requires configured credentials and an approved ledger record.

## Course Concept Coverage

- **Day 1: Agentic SDLC + vibe coding** - behavior is captured in `.agents-cli-spec.md`, then implemented as an ADK prototype.
- **Day 2: Tools + interoperability** - each external system is modeled as a typed adapter/tool; the same tools are exposed through a local stdio MCP server.
- **Day 3: Multi-agent systems + skills** - the coordinator delegates to specialist ADK sub-agents and repo-native `SKILL.md` packages document the reusable capabilities.
- **Day 4: Security + evaluation** - external writes are approval-gated, evidence is preserved, and evals check safety-sensitive behavior.
- **Day 5: Production-grade development** - scaffolded with Agents CLI, includes a spec, tests, eval cases, and a deployment path.

## Architecture

```text
User / ADK Playground
        |
        v
Workstream Control Agent
        |
        +-- ADK specialist sub-agents
        |     +-- source_intake_agent
        |     +-- reconciliation_agent
        |     +-- github_pr_agent
        |     +-- connector_draft_agent
        |     +-- security_approval_agent
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

An editable SVG diagram is available at `docs/architecture-work-buddy.svg`. Drag it into Figma to create a shareable design file; import notes are in `docs/figma-import-notes.md`.

## Multi-Agent System

`app/agent.py` defines the root coordinator. `app/sub_agents.py` defines five ADK specialist agents:

- `source_intake_agent` - ingests meeting, Slack, email, Jira, GitHub, and freeform sources, then extracts work items.
- `reconciliation_agent` - reconciles duplicate candidates, records conflicts, and updates project memory.
- `github_pr_agent` - inspects local repo state and drafts GitHub PR artifacts.
- `connector_draft_agent` - drafts Jira, Slack, and email updates through mock adapters.
- `security_approval_agent` - enforces approval policy and blocks unsafe external writes.

The coordinator can call tools directly or delegate focused work to these specialists.

## MCP Server

The project includes a dependency-free local stdio MCP server in `app/mcp_server.py`. It exposes the ledger and connector tools through MCP-style `tools/list` and `tools/call` methods.

Run it locally:

```powershell
python -m app.mcp_server
```

Example MCP request:

```json
{"jsonrpc":"2.0","id":1,"method":"tools/list"}
```

Example tool call:

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ingest_source","arguments":{"content":"Action: draft the release PR.","source_type":"freeform","metadata_json":"{}"}}}
```

This gives the capstone a real MCP-compatible bridge while keeping live Jira/Slack/GitHub credentials out of v1.

## Agent Skills

Reusable skills live under `skills/`:

- `meeting_task_extractor`
- `cross_source_reconciler`
- `decision_logger`
- `github_pr_writer`
- `memory_updater`
- `approval_guard`
- `security_redactor`

Each skill has a `SKILL.md` with when-to-use guidance, expected inputs, tool flow, and safety rules. The ADK sub-agents implement these capabilities in code.

Key files:

- `.agents-cli-spec.md` - product/spec source of truth.
- `app/agent.py` - ADK agent definition, model selection, instructions, tool wiring.
- `app/sub_agents.py` - ADK specialist sub-agents.
- `app/mcp_server.py` - local stdio MCP server for ledger/connectors.
- `app/live_connectors.py` - optional Slack/Jira/GitHub/SMTP execution after approval.
- `app/tools.py` - typed agent tools and mock adapters.
- `app/ledger.py` - local ledger, task reconciliation, memory, PR drafts, approvals, redaction.
- `skills/*/SKILL.md` - reusable agent skills from the course.
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

Generated `ledger/` contents are ignored by Git. Commit curated demo ledger examples separately if needed.

## Permissions Model

The v1 policy is conservative:

- Local ledger and memory updates are allowed.
- Drafting Jira, Slack, email, and GitHub artifacts is allowed.
- Posting Slack, sending email, updating Jira, pushing branches, opening PRs, merging PRs, or marking external work complete requires a `request_approval` record.
- Optional live execution requires `record_human_approval` with the exact confirmation phrase, then `execute_approved_action`.
- The agent must cite source evidence for task and status changes when available.
- The agent must record conflicts instead of silently choosing between inconsistent facts.

## Optional Live Connectors

By default, Work Buddy drafts actions and creates approval records. If you want to test live execution, configure the relevant environment variables and approve the action first.

Slack:

```bash
export SLACK_BOT_TOKEN="xoxb-..."
```

```powershell
$env:SLACK_BOT_TOKEN = "xoxb-..."
```

Jira:

```bash
export JIRA_BASE_URL="https://your-domain.atlassian.net"
export JIRA_EMAIL="you@example.com"
export JIRA_API_TOKEN="..."
```

```powershell
$env:JIRA_BASE_URL = "https://your-domain.atlassian.net"
$env:JIRA_EMAIL = "you@example.com"
$env:JIRA_API_TOKEN = "..."
```

GitHub PR creation:

```bash
export GITHUB_TOKEN="ghp_..."
export GITHUB_REPOSITORY="owner/repo"
```

```powershell
$env:GITHUB_TOKEN = "ghp_..."
$env:GITHUB_REPOSITORY = "owner/repo"
```

SMTP email:

```bash
export SMTP_HOST="smtp.example.com"
export SMTP_PORT="587"
export SMTP_USERNAME="you@example.com"
export SMTP_PASSWORD="..."
export SMTP_FROM="you@example.com"
```

```powershell
$env:SMTP_HOST = "smtp.example.com"
$env:SMTP_PORT = "587"
$env:SMTP_USERNAME = "you@example.com"
$env:SMTP_PASSWORD = "..."
$env:SMTP_FROM = "you@example.com"
```

Approval flow:

1. Draft action with a mock connector or `request_approval`.
2. Record approval with `record_human_approval`.
3. The confirmation phrase must be exactly `I approve this external action`.
4. Execute with `execute_approved_action`.

If credentials are missing, execution records `not_configured` rather than silently pretending it succeeded.

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

Linux/macOS:

```bash
export WORKSTREAM_MODEL_PROVIDER="gemini"
export WORKSTREAM_MODEL="gemini-flash-latest"
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
agents-cli playground
```

Windows PowerShell:

```powershell
$env:WORKSTREAM_MODEL_PROVIDER = "gemini"
$env:WORKSTREAM_MODEL = "gemini-flash-latest"
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
agents-cli playground
```

### OpenAI

Linux/macOS:

```bash
export WORKSTREAM_MODEL_PROVIDER="openai"
export WORKSTREAM_MODEL="gpt-4o-mini"
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
agents-cli playground
```

Windows PowerShell:

```powershell
$env:WORKSTREAM_MODEL_PROVIDER = "openai"
$env:WORKSTREAM_MODEL = "gpt-4o-mini"
$env:OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
agents-cli playground
```

The code maps that to `openai/gpt-4o-mini` for LiteLLM.

### Claude

Linux/macOS:

```bash
export WORKSTREAM_MODEL_PROVIDER="claude"
export WORKSTREAM_MODEL="claude-3-5-sonnet-latest"
export ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"
agents-cli playground
```

Windows PowerShell:

```powershell
$env:WORKSTREAM_MODEL_PROVIDER = "claude"
$env:WORKSTREAM_MODEL = "claude-3-5-sonnet-latest"
$env:ANTHROPIC_API_KEY = "YOUR_ANTHROPIC_API_KEY"
agents-cli playground
```

The code maps that to `anthropic/claude-3-5-sonnet-latest` for LiteLLM.

### Ollama / Local Open-Source

Start Ollama separately, then run:

Linux/macOS:

```bash
export WORKSTREAM_MODEL_PROVIDER="ollama"
export WORKSTREAM_MODEL="llama3.1"
export PYTHONUTF8="1"
agents-cli playground
```

Windows PowerShell:

```powershell
$env:WORKSTREAM_MODEL_PROVIDER = "ollama"
$env:WORKSTREAM_MODEL = "llama3.1"
$env:PYTHONUTF8 = "1"
agents-cli playground
```

The code maps that to `ollama_chat/llama3.1` for LiteLLM. For reliable agent tools, choose a local model/server that supports tool/function calling.

### vLLM or OpenAI-Compatible Endpoint

Linux/macOS:

```bash
export WORKSTREAM_MODEL_PROVIDER="litellm"
export WORKSTREAM_MODEL="openai/my-served-model"
export OPENAI_API_BASE="https://your-vllm-endpoint.example.com/v1"
export OPENAI_API_KEY="YOUR_ENDPOINT_KEY"
agents-cli playground
```

Windows PowerShell:

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

Install dependencies on Linux/macOS:

```bash
agents-cli install
```

Install dependencies on Windows PowerShell:

```powershell
agents-cli install
```

Run deterministic tests on Linux/macOS:

```bash
uv run pytest tests/unit tests/integration/test_agent.py
```

Run deterministic tests on Windows PowerShell:

```powershell
uv run pytest tests\unit tests\integration\test_agent.py
```

Run lint on Linux/macOS or Windows:

```bash
uv run --extra lint ruff check .
```

Launch the ADK playground:

```bash
agents-cli playground
```

## Dashboard UI

Work Buddy includes a lightweight web dashboard served by FastAPI at `/ui`.

Run locally on Linux/macOS:

```bash
uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000
```

Run locally on Windows PowerShell:

```powershell
uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/ui
```

The dashboard supports:

- processing work dumps into tasks and memory
- viewing tasks, approvals, PR drafts, events, and memory
- drafting Slack/Jira/email approvals
- approving/rejecting/executing approval records
- checking connector environment configuration

The ADK chat playground is still available separately through `agents-cli playground`.

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

## Cloud Run Hosting

The dashboard and backend can be hosted as one Cloud Run service. Full details are in `docs/cloud-run-deploy.md`.

You need to log in before deployment:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Enable required APIs:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com aiplatform.googleapis.com
```

Deploy from this repo:

```bash
gcloud run deploy work-buddy \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 2 \
  --memory 2Gi \
  --cpu 1 \
  --set-env-vars WORKSTREAM_MODEL_PROVIDER=gemini,WORKSTREAM_MODEL=gemini-flash-latest
```

Get the service URL:

```bash
gcloud run services describe work-buddy \
  --region us-central1 \
  --format 'value(status.url)'
```

Open the dashboard at:

```text
https://SERVICE_URL/ui
```

Cost note: Cloud Run has a monthly free tier for low-traffic services, but model calls, Secret Manager, logs, and network usage can still create charges. Keep `min-instances=0` for the lowest demo cost.

## Roadmap

- Live Jira API connector.
- Live Slack OAuth app and message posting after approval.
- Gmail/Google Workspace ingestion and send-after-approval.
- GitHub branch/PR creation after approval.
- MCP servers for connector portability.
- Scheduled workstream digest on Cloud Run.
- Cloud SQL or managed memory backend for multi-user production use.
