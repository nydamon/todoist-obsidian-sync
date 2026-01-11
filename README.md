# Todoist-Obsidian Sync

Real-time bidirectional sync between Todoist and Obsidian via webhooks.

## Features

- **URL Detection & Routing**: Automatically detects URL types and routes to appropriate AI model
  - X/Twitter threads → Grok 4 Fast (xAI)
  - YouTube videos → Gemini 3 Flash (OpenRouter)
  - Articles → Claude Sonnet 4.5 (OpenRouter)

- **AI Summarization**: Extracts title, summary, and key points from URLs

- **Obsidian Integration**: Creates formatted notes with frontmatter in your GitHub-synced vault

- **Project Sync**: Mirrors Todoist project structure to Obsidian folders

## Setup

### 1. Install dependencies

```bash
cd todoist-obsidian-sync
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

### 3. Run locally

```bash
python main.py
```

Server runs at `http://localhost:8000`

### 4. Test endpoints

**Test summarization:**
```bash
curl -X POST "http://localhost:8000/test/summarize?url=https://x.com/elonmusk/status/1877520382027026515"
```

**Test note creation:**
```bash
curl -X POST "http://localhost:8000/test/create-note?url=https://www.paulgraham.com/greatwork.html&project=TCP"
```

## Webhook Setup (Production)

1. Deploy to Railway
2. Set up Todoist webhook at: https://developer.todoist.com/sync/v9/#webhooks
3. Point webhook URL to: `https://your-app.railway.app/webhook/todoist`
4. Set `VERIFY_WEBHOOK=true` in production

## Project Structure

```
todoist-obsidian-sync/
├── main.py           # FastAPI server & webhook handlers
├── summarizer.py     # AI summarization (Grok, Gemini, Claude)
├── github_sync.py    # GitHub/Obsidian integration
├── todoist_client.py # Todoist API wrapper
├── url_utils.py      # URL detection utilities
├── requirements.txt
├── .env.example
└── README.md
```

## Folder Mapping

| Todoist Project | Obsidian Folder |
|-----------------|-----------------|
| Inbox | Projects/_Inbox/ |
| Personal/Family | Personal/Family/ |
| Personal/Golf Courses | Personal/Golf Courses/ |
| TCP | Projects/TCP/ |
| Classic-Clarity-Press | Projects/Classic-Clarity-Press/ |

## Note Template

```markdown
---
source: <url>
captured: 2025-01-11
status: new
type: x-thread | youtube | article
todoist_id: <task_id>
---

# 🆕 Title Here

## Summary
...

## Key Points
- ...

## Source
[Original](<url>)
```
