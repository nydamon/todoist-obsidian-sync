# Todoist-Obsidian Sync

> Capture. Summarize. Sync. Transform fleeting links into permanent knowledge.

## The Vision

This project bridges the gap between **capturing** (Todoist) and **thinking** (Obsidian). When you save a link in Todoist, the system:

1. Detects the URL type (X/Twitter thread, YouTube video, or article)
2. Routes to the optimal AI model for that content type
3. Generates a beautifully formatted, AI-summarized note
4. Commits it to your Obsidian vault via GitHub

**The goal:** Zero-friction knowledge capture. Save a link, get a note.

---

## Architecture

```
Todoist Webhook → FastAPI → URL Detection → AI Summarization → GitHub/Obsidian
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `main.py` | FastAPI webhook server, event routing, test endpoints |
| `url_utils.py` | URL detection and type classification |
| `summarizer.py` | AI model orchestration and response parsing |
| `github_sync.py` | Obsidian vault file operations via GitHub API |
| `todoist_client.py` | Todoist API wrapper with project hierarchy caching |

### AI Model Routing

| Content Type | Model | Why |
|-------------|-------|-----|
| X/Twitter threads | Grok 4 Fast (xAI) | Native understanding of Twitter/X content |
| YouTube videos | Gemini 3 Flash (OpenRouter) | Strong video/transcript comprehension |
| Articles | Claude Sonnet 4.5 (OpenRouter) | Superior long-form text analysis |

---

## Key Patterns

### 1. Event-Driven Architecture
All operations trigger from Todoist webhooks. The server is stateless—state lives in Todoist and GitHub.

### 2. Folder Mapping Convention
```
Inbox projects     → Projects/_Inbox/
Personal/* projects → Personal/{project}/
All other projects  → Projects/{project}/
```

### 3. Note Filename Format
```
🆕 YYYY-MM-DD-{slugified-title}.md
```

### 4. YAML Frontmatter Structure
Every note includes metadata for Obsidian queries:
```yaml
---
source: <url>
captured: YYYY-MM-DD
status: new
type: x-thread|youtube|article
todoist_id: <task_id>
# + type-specific metadata
---
```

### 5. Robust JSON Parsing
LLM responses are unpredictable. `summarizer.py` uses regex fallback extraction when JSON parsing fails.

---

## Development

### Local Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure your keys
python main.py
```

### Test Endpoints
```bash
# Test summarization only
curl -X POST "http://localhost:8000/test/summarize?url=<URL>"

# Test full note creation workflow
curl -X POST "http://localhost:8000/test/create-note?url=<URL>&project=Inbox"
```

### Required Environment Variables
- `TODOIST_API_KEY` - Todoist API token
- `XAI_API_KEY` - xAI (Grok) API key
- `OPENROUTER_API_KEY` - OpenRouter API key
- `GITHUB_TOKEN` - GitHub personal access token
- `GITHUB_REPO` - Target repo (e.g., `nydamon/obsidian`)
- `WEBHOOK_SECRET` - Todoist webhook verification secret

---

## Making Changes

### Adding a New URL Type
1. Add pattern to `URLType` enum in `url_utils.py`
2. Add regex detection in `detect_url_type()`
3. Add model routing in `summarizer.py`
4. Update prompt template for the new content type
5. Add type-specific frontmatter fields in `github_sync.py`

### Adding a New AI Model
1. Add API configuration in `summarizer.py`
2. Create summarization method following existing pattern
3. Update routing logic in `summarize_url()`
4. Handle model-specific response parsing

### Modifying Note Format
- Frontmatter: `github_sync.py` → `create_note()`
- Filename: `github_sync.py` → `_generate_filename()`
- Body structure: `github_sync.py` → `_format_note_content()`

---

## Error Handling Philosophy

1. **Fail gracefully** - A failed summarization shouldn't crash the webhook
2. **Log verbosely** - Print statements for debugging (upgrade to proper logging as needed)
3. **Verify signatures in production** - `VERIFY_WEBHOOK` environment flag
4. **Cache project data** - Minimize Todoist API calls

---

## Testing Checklist

Before deploying changes:
- [ ] Test X/Twitter thread summarization
- [ ] Test YouTube video summarization
- [ ] Test article summarization
- [ ] Verify GitHub commit works
- [ ] Check folder mapping logic
- [ ] Validate frontmatter format
- [ ] Test webhook signature verification

---

## Production Notes

- **Platform:** Railway (or any platform supporting Python/ASGI)
- **Webhook URL:** `https://<your-domain>/webhook/todoist`
- **Signature verification:** Enable via `VERIFY_WEBHOOK=true`
- **Background tasks:** FastAPI BackgroundTasks handles async processing

---

## Future Considerations

- Formal test suite with pytest
- Structured logging (replace print statements)
- Rate limiting for API calls
- Retry logic for transient failures
- Support for additional URL types (podcasts, PDFs, etc.)
- Obsidian plugin for bidirectional sync
