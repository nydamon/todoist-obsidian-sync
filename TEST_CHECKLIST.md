# Test Checklist

Manual testing checklist for the Todoist-Obsidian Sync system.

## Pre-Deployment Tests

### 1. Health Check
```bash
curl http://localhost:8000/health
```
Expected: `{"status": "healthy"}`

### 2. X/Twitter Thread Summarization
```bash
curl -X POST "http://localhost:8000/test/summarize?url=https://x.com/user/status/123456789"
```
Verify:
- [ ] Uses Grok 4 Fast model
- [ ] Returns author handle
- [ ] Returns thread date if available
- [ ] Key points include inline links (format: `[→](url)`)

### 3. YouTube Video Summarization
```bash
curl -X POST "http://localhost:8000/test/summarize?url=https://www.youtube.com/watch?v=VIDEO_ID"
```
Verify:
- [ ] Uses Gemini 3 Flash model
- [ ] Returns channel name
- [ ] Returns video duration if available
- [ ] Key points include inline links to referenced resources

### 4. Article Summarization
```bash
curl -X POST "http://localhost:8000/test/summarize?url=https://example.com/article"
```
Verify:
- [ ] Uses Claude Sonnet 4.5 model
- [ ] Jina Reader fetches content (check logs for content length)
- [ ] Returns author/publication if available
- [ ] Key points include inline links from article
- [ ] Fallback works when Jina Reader fails

### 5. Note Creation
```bash
curl -X POST "http://localhost:8000/test/create-note?url=https://example.com/article&project=Inbox"
```
Verify:
- [ ] Creates file in GitHub repo
- [ ] File appears in correct folder (`_Inbox` for Inbox)
- [ ] Filename format: `YYYY-MM-DD-{slug}.md`
- [ ] YAML frontmatter includes all fields
- [ ] Links in key points are clickable

### 6. Research Note (No URL)
```bash
curl -X POST "http://localhost:8000/test/research-note?topic=Machine%20Learning&project=Learning"
```
Verify:
- [ ] Creates research note without URL
- [ ] Includes "To Explore" section with suggestions
- [ ] Folder context affects content (e.g., "Learning" context)

### 7. Folder Mapping
```bash
curl http://localhost:8000/debug/folder-mapping
```
Verify:
- [ ] Root folders correctly identified
- [ ] Nested projects map correctly
- [ ] Inbox maps to `_Inbox`

## Webhook Tests

### 8. Task with URL
Create a Todoist task with a URL in the content or description.

Verify:
- [ ] Webhook received (check logs)
- [ ] URL extracted correctly
- [ ] Note created in Obsidian vault
- [ ] Correct folder based on project

### 9. Task with @note Label
Create a Todoist task with `@note` label (no URL).

Verify:
- [ ] Research note created
- [ ] Folder context applied based on project

### 10. New Project
Create a new project in Todoist.

Verify:
- [ ] Folder created in vault (via `.gitkeep`)

## Error Handling Tests

### 11. Invalid URL
```bash
curl -X POST "http://localhost:8000/test/summarize?url=not-a-valid-url"
```
Verify:
- [ ] Graceful error handling
- [ ] No crash

### 12. API Failure
Set invalid API key temporarily and test.

Verify:
- [ ] Error logged to `_System/Error-Logs`
- [ ] Webhook doesn't crash

### 13. Rate Limiting (Jina Reader)
Rapid-fire multiple article requests.

Verify:
- [ ] Retry logic kicks in (check logs for "Rate limited" warnings)
- [ ] Exponential backoff works (1s, 2s, 4s delays)

## Logging Tests

### 14. Log Levels
Set `LOG_LEVEL=DEBUG` and run tests.

Verify:
- [ ] Debug messages visible (Jina content fetch details)
- [ ] Info messages for successful operations
- [ ] Warning messages for retries/fallbacks
- [ ] Error messages for failures

## Post-Deployment Verification

- [ ] Railway deployment shows healthy status
- [ ] Todoist webhook URL configured correctly
- [ ] Test task triggers full workflow
- [ ] Note appears in Obsidian vault via GitHub sync
