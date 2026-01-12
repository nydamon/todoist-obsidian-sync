# Setup Guide

Complete setup guide for deploying the Todoist-Obsidian Sync service.

## Prerequisites

- Python 3.9+
- A Todoist account with API access
- A GitHub account with a repository for your Obsidian vault
- API keys for AI services (xAI, OpenRouter)

## 1. Clone the Repository

```bash
git clone https://github.com/your-username/todoist-obsidian-sync.git
cd todoist-obsidian-sync
```

## 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Required variables:

| Variable | Description | How to Get |
|----------|-------------|------------|
| `TODOIST_API_KEY` | Your Todoist API token | [Todoist Settings → Integrations → Developer](https://todoist.com/prefs/integrations) |
| `XAI_API_KEY` | xAI (Grok) API key | [x.ai Console](https://console.x.ai/) |
| `OPENROUTER_API_KEY` | OpenRouter API key | [OpenRouter Keys](https://openrouter.ai/keys) |
| `GITHUB_TOKEN` | GitHub Personal Access Token | [GitHub Settings → Developer Settings → Personal Access Tokens](https://github.com/settings/tokens) |
| `GITHUB_REPO` | Target repository (e.g., `username/obsidian`) | Your Obsidian vault repo |
| `WEBHOOK_SECRET` | Secret for webhook verification | Generate a random string |

Optional variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `VERIFY_WEBHOOK` | `false` | Enable webhook signature verification in production |

### GitHub Token Permissions

Your GitHub token needs these permissions:
- `repo` (Full control of private repositories)
- Or for public repos: `public_repo`

### OpenRouter Model Access

Ensure your OpenRouter account has access to:
- `anthropic/claude-sonnet-4.5` (for articles)
- `google/gemini-3-flash-preview` (for YouTube)

## 4. Local Development

Start the server:

```bash
python main.py
```

The server runs on `http://localhost:8000`.

### Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Test summarization
curl -X POST "http://localhost:8000/test/summarize?url=https://example.com/article"

# Test note creation
curl -X POST "http://localhost:8000/test/create-note?url=https://example.com/article&project=Inbox"
```

## 5. Todoist Webhook Setup

### Create a Todoist App

1. Go to [Todoist App Console](https://developer.todoist.com/appconsole.html)
2. Create a new app
3. Set OAuth Redirect URL to: `https://your-domain.com/oauth/callback`
4. Copy the Client Secret → use as `WEBHOOK_SECRET`

### Configure Webhooks

1. In your Todoist app settings, enable webhooks
2. Set Webhook URL to: `https://your-domain.com/webhook/todoist`
3. Select events:
   - `item:added` (required - triggers note creation)
   - `item:completed` (optional - for archiving)
   - `project:added` (optional - folder creation)
   - `project:deleted` (optional - folder archival)

### Authorize Your Account

Visit the OAuth authorization URL for your app to activate webhooks for your account.

## 6. Production Deployment (Railway)

### Deploy to Railway

1. Connect your GitHub repository to Railway
2. Railway auto-detects the Python project
3. Add environment variables in Railway dashboard
4. Deploy!

### Railway Configuration

Railway should auto-detect these settings:
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

If not, create a `railway.toml`:

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
```

### Environment Variables in Railway

Set all variables from step 3 in Railway's Variables tab. Additionally set:
- `VERIFY_WEBHOOK=true` (enable in production)

### Custom Domain (Optional)

1. Add a custom domain in Railway settings
2. Update Todoist webhook URL to your custom domain

## 7. Verify Deployment

1. Check Railway logs for startup success
2. Test health endpoint: `curl https://your-app.railway.app/health`
3. Create a test task in Todoist with a URL
4. Verify note appears in your GitHub/Obsidian repo

## Troubleshooting

### Webhook Not Triggering

- Verify webhook URL is correct in Todoist app settings
- Check Railway logs for incoming requests
- Ensure OAuth authorization was completed

### Note Not Created

- Check Railway logs for errors
- Verify GitHub token has correct permissions
- Check `_System/Error-Logs` folder in your vault

### AI Summarization Failing

- Verify API keys are correct
- Check OpenRouter model access
- Look for rate limiting in logs (Jina Reader has retry logic)

### Debugging

Enable debug logging:
```
LOG_LEVEL=DEBUG
```

This shows:
- Full webhook payloads
- Jina Reader fetch attempts
- Content lengths and processing details

## Architecture Reference

```
Todoist Task Created
       ↓
   Webhook POST
       ↓
  URL Detection
       ↓
┌──────┴──────┐
│   X/Twitter │ → Grok 4 Fast
│   YouTube   │ → Gemini 3 Flash
│   Article   │ → Jina Reader → Claude Sonnet 4.5
│   @note     │ → Claude Sonnet 4.5 (research)
└──────┬──────┘
       ↓
  GitHub Commit
       ↓
  Obsidian Sync
```
