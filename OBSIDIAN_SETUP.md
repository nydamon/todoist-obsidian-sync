# Obsidian Setup Guide

Complete the sync loop by configuring Obsidian to pull notes from GitHub.

## Prerequisites

- Obsidian vault synced with GitHub (nydamon/obsidian)
- Pushover app installed on iOS/macOS ($5 one-time) — optional but recommended

---

## 1. Obsidian Git Plugin

The Git plugin automatically pulls new notes from GitHub into your local vault.

### Installation

1. Settings → Community plugins → Browse
2. Search "Git" → Install **Obsidian Git**
3. Enable the plugin

### Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| Auto pull interval (minutes) | `1` | Pulls new notes every minute |
| Auto push interval (minutes) | `0` | Disable unless you want local edits pushed |
| Pull on startup | `Enabled` | Sync when opening Obsidian |
| Auto commit interval | `0` or `60` | Your preference |

### Verify It's Working

- Status bar should show "Git: pull: everything is up-to-date"
- Open Command palette (`Cmd+P`) → type "Git" to see available commands
- Manual test: Run `Git: Pull` — should succeed without errors

---

## 2. Inbox Plugin (Local Notifications)

The Inbox plugin monitors your `_Inbox` folder and alerts you when new content arrives.

### Installation

1. Settings → Community plugins → Browse
2. Search "Inbox" by **Zachatoo** → Install
3. Enable the plugin

### Configuration

- Set inbox folder to `_Inbox`
- Enable notifications for new content
- Customize comparison settings as needed

---

## 3. Pushover Setup (Server Notifications)

Get instant push notifications when notes are created or when errors occur.

### Get Your Keys

1. Create account at [pushover.net](https://pushover.net)
2. Purchase the app for your platform ($5 one-time)
3. **Register an application** → copy the **API Token**
4. Copy your **User Key** from the dashboard

### Configure Server

Add to Railway environment variables:

```
PUSHOVER_APP_TOKEN=your_api_token_here
PUSHOVER_USER_KEY=your_user_key_here
```

Optional: Set your vault name if different from default:

```
OBSIDIAN_VAULT_NAME=My Vault
```

### What You'll Receive

| Event | Notification |
|-------|-------------|
| Note created | "📝 {title}" with link to open in Obsidian |
| Error occurred | "⚠️ {error type}" with details |

### Test

1. Create a Todoist task with a URL
2. You should receive:
   - **Pushover notification** within ~10 seconds
   - **Note in Obsidian** within ~60 seconds (next Git pull)

---

## 4. Recommended Dataview Queries

Add these to a dashboard note to track your captures.

### Today's Captures

```dataview
TABLE source, type
FROM "_Inbox"
WHERE captured = date(today)
SORT file.ctime DESC
```

### Unread Notes

```dataview
LIST
FROM "_Inbox"
WHERE status = "new"
SORT file.ctime DESC
```

### Recent Errors

```dataview
TABLE error_type, timestamp
FROM "_System/Error-Logs"
WHERE status = "unresolved"
SORT timestamp DESC
LIMIT 10
```

### Notes by Type

```dataview
TABLE rows.file.link as Notes
FROM "_Inbox"
GROUP BY type
```

---

## Troubleshooting

### Git commands not showing in Command Palette

- Go to Settings → Community plugins
- Toggle the Git plugin off, then back on
- Restart Obsidian

### Pull says "up-to-date" but missing notes

1. **Check GitHub directly** — is the note in the repo?
2. If **not in GitHub**: Server issue (check Railway logs)
3. If **in GitHub**: Branch mismatch or auth issue

### No Pushover notifications

1. Verify environment variables are set in Railway:
   - `PUSHOVER_APP_TOKEN`
   - `PUSHOVER_USER_KEY`
2. Check Railway logs for "Pushover notification" messages
3. Test Pushover directly at pushover.net

### Notes appearing in wrong folder

Check the folder mapping logic:

```
GET /debug/folder-mapping
```

This shows how Todoist projects map to Obsidian folders.

---

## Timing Expectations

```
You add Todoist task with URL
        ↓ (instant)
Webhook fires to server
        ↓ (~5-10 sec)
Server processes + creates note in GitHub
        ↓ (instant)
Pushover notification arrives
        ↓ (up to 60 sec)
Obsidian Git pulls new note
        ↓
Note appears in vault
```

**Worst case delay:** ~70 seconds
**Average delay:** ~30-40 seconds

---

## Environment Variables Reference

### Required (Server)

```
TODOIST_API_KEY=
XAI_API_KEY=
OPENROUTER_API_KEY=
GITHUB_TOKEN=
GITHUB_REPO=nydamon/obsidian
WEBHOOK_SECRET=
JINA_API_KEY=
```

### Optional (Notifications)

```
PUSHOVER_APP_TOKEN=        # From Pushover app dashboard
PUSHOVER_USER_KEY=         # From Pushover user settings
OBSIDIAN_VAULT_NAME=       # Default: "Obsidian Vault"
```
