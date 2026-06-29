# Cloud Run Deployment

Work Buddy can be hosted as a single Cloud Run service. The FastAPI backend serves both:

- ADK API routes
- the lightweight dashboard at `/ui`

## Prerequisites

Install:

- Google Cloud SDK
- Docker support through Cloud Build
- A Google Cloud project with billing enabled

Authenticate:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Enable APIs:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com aiplatform.googleapis.com
```

## Deploy From Source

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

Open the dashboard:

```bash
gcloud run services describe work-buddy \
  --region us-central1 \
  --format 'value(status.url)'
```

Then visit:

```text
https://SERVICE_URL/ui
```

## Connector Secrets

For production, store connector credentials in Secret Manager and map them to environment variables.

Create secrets:

```bash
printf '%s' 'xoxb-your-token' | gcloud secrets create SLACK_BOT_TOKEN --data-file=-
printf '%s' 'your-jira-token' | gcloud secrets create JIRA_API_TOKEN --data-file=-
printf '%s' 'your-github-token' | gcloud secrets create GITHUB_TOKEN --data-file=-
```

Deploy with secrets:

```bash
gcloud run deploy work-buddy \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --set-secrets SLACK_BOT_TOKEN=SLACK_BOT_TOKEN:latest,JIRA_API_TOKEN=JIRA_API_TOKEN:latest,GITHUB_TOKEN=GITHUB_TOKEN:latest \
  --set-env-vars JIRA_BASE_URL=https://your-domain.atlassian.net,JIRA_EMAIL=you@example.com,GITHUB_REPOSITORY=owner/repo
```

## Cost Notes

For a small capstone demo, Cloud Run can often stay within the free tier if:

- `min-instances` is `0`
- traffic is low
- memory/CPU are modest
- model/API usage is limited

Model calls, Secret Manager usage, logging, and outbound traffic may still cost money.
