"""
FastAPI webhook server for Todoist events
"""
import os
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from dotenv import load_dotenv

from url_utils import detect_url_type, extract_url_from_text
from summarizer import AISummarizer
from github_sync import ObsidianGitHub
from todoist_client import TodoistClient
from error_logger import log_error

load_dotenv()

app = FastAPI(title="Todoist-Obsidian Sync")

# Initialize clients
summarizer = AISummarizer()
todoist = TodoistClient()
github = ObsidianGitHub(todoist_client=todoist)  # Pass todoist for dynamic folder mapping


def verify_webhook(payload: bytes, signature: str) -> bool:
    """Verify Todoist webhook signature"""
    secret = os.getenv("WEBHOOK_SECRET", "").encode()
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def process_new_task(task_id: str):
    """Process a new task - extract URL, summarize, create note"""
    
    # Get task details
    task = todoist.get_task(task_id)
    if not task:
        log_error(
            error_type="Task Not Found",
            error_message=f"Could not retrieve task from Todoist",
            context={"task_id": task_id}
        )
        print(f"Task {task_id} not found")
        return
    
    # Check for @note label (research note without URL)
    has_note_label = "note" in [l.lower() for l in task.labels]
    
    # Check for URL in content or description
    url = extract_url_from_text(task.content) or extract_url_from_text(task.description)
    
    if has_note_label and not url:
        # Create research note for @note tasks without URLs
        print(f"Processing @note task: {task.content}")
        
        try:
            # Use task content as topic, pass project context
            research = await summarizer.research_topic(
                topic=task.content,
                project_name=task.project_name,
                parent_project=task.parent_project_name,
                context=task.description
            )
            
            file_path = github.create_research_note(
                research=research,
                project_name=task.project_name,
                parent_project=task.parent_project_name,
                todoist_task_id=task.id,
                priority=task.priority
            )
            print(f"Created research note: {file_path}")
        except Exception as e:
            log_error(
                error_type="Research Note Failed",
                error_message=str(e),
                context={
                    "task_id": task_id,
                    "task_content": task.content,
                    "project": task.project_name,
                    "parent_project": task.parent_project_name
                },
                exception=e
            )
            print(f"Error creating research note: {e}")
        return
    
    if not url:
        print(f"No URL found in task {task_id} (add @note label for research notes)")
        return
    
    # Detect URL type
    url_type = detect_url_type(url)
    print(f"Processing {url_type.value}: {url}")
    
    # Summarize
    try:
        summary = await summarizer.summarize(url, url_type)
    except Exception as e:
        log_error(
            error_type="Summarization Failed",
            error_message=str(e),
            context={
                "task_id": task_id,
                "url": url,
                "url_type": url_type.value,
                "project": task.project_name
            },
            exception=e
        )
        print(f"Error summarizing: {e}")
        return
    
    # Create note in Obsidian
    try:
        file_path = github.create_note(
            summary=summary,
            project_name=task.project_name,
            parent_project=task.parent_project_name,
            todoist_task_id=task.id,
            priority=task.priority
        )
        print(f"Created note: {file_path}")
    except Exception as e:
        log_error(
            error_type="Note Creation Failed",
            error_message=str(e),
            context={
                "task_id": task_id,
                "url": url,
                "title": summary.title,
                "project": task.project_name
            },
            exception=e
        )
        print(f"Error creating note: {e}")
        return
    
    # Optionally complete the task
    # todoist.complete_task(task_id)


async def process_task_completed(task_id: str):
    """Archive note when task is completed"""
    # This would require storing a mapping of task_id -> file_path
    # For now, we'll skip this
    print(f"Task completed: {task_id}")


async def process_project_added(project_id: str):
    """Create folder when project is added"""
    project = todoist.get_project(project_id)
    if not project:
        return
    
    folder_path = github._get_folder_path(project.name, project.parent_name)
    github.create_folder(folder_path)
    print(f"Created folder: {folder_path}")


async def process_project_deleted(project_id: str, project_name: str):
    """Archive folder when project is deleted"""
    # Note: We'd need to track the project name since it's deleted
    print(f"Project deleted: {project_id}")


@app.post("/webhook/todoist")
async def todoist_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle Todoist webhook events"""
    
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify signature (optional in dev)
    signature = request.headers.get("X-Todoist-Hmac-SHA256", "")
    if os.getenv("VERIFY_WEBHOOK", "false").lower() == "true":
        if not verify_webhook(body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse event
    event = await request.json()
    event_name = event.get("event_name")
    event_data = event.get("event_data", {})
    
    print(f"Received event: {event_name}")
    
    # Route to handler
    if event_name == "item:added":
        background_tasks.add_task(process_new_task, event_data.get("id"))
    
    elif event_name == "item:completed":
        background_tasks.add_task(process_task_completed, event_data.get("id"))
    
    elif event_name == "project:added":
        background_tasks.add_task(process_project_added, event_data.get("id"))
    
    elif event_name == "project:deleted":
        background_tasks.add_task(
            process_project_deleted, 
            event_data.get("id"),
            event_data.get("name", "")
        )
    
    return {"status": "ok"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/oauth/callback")
async def oauth_callback(code: str = None, state: str = None, error: str = None):
    """OAuth callback endpoint - just confirms authorization was successful"""
    if error:
        return {"status": "error", "message": error}

    if code:
        # We don't need to exchange the code - just completing OAuth activates webhooks
        return {
            "status": "success",
            "message": "Authorization complete! Webhooks are now active for your account.",
            "code_received": True
        }

    return {"status": "waiting", "message": "No authorization code received"}


@app.post("/test/summarize")
async def test_summarize(url: str):
    """Test endpoint to summarize a URL"""
    url_type = detect_url_type(url)
    summary = await summarizer.summarize(url, url_type)
    return {
        "url_type": url_type.value,
        "title": summary.title,
        "summary": summary.summary,
        "key_points": summary.key_points,
        "metadata": summary.extra_metadata
    }


@app.post("/test/create-note")
async def test_create_note(url: str, project: str = "Inbox", parent: str = None, priority: int = 4):
    """Test endpoint to create a note from URL"""
    url_type = detect_url_type(url)
    summary = await summarizer.summarize(url, url_type)
    file_path = github.create_note(
        summary=summary,
        project_name=project,
        parent_project=parent,
        priority=priority
    )
    return {
        "file_path": file_path,
        "title": summary.title
    }


@app.post("/test/research-note")
async def test_research_note(topic: str, project: str = "Inbox", parent: str = None, 
                              context: str = "", priority: int = 4):
    """Test endpoint to create a research note (simulates @note label)"""
    research = await summarizer.research_topic(
        topic=topic,
        project_name=project,
        parent_project=parent or "",
        context=context
    )
    file_path = github.create_research_note(
        research=research,
        project_name=project,
        parent_project=parent,
        priority=priority
    )
    return {
        "file_path": file_path,
        "title": research.title,
        "summary": research.summary,
        "key_points": research.key_points,
        "suggestions": research.suggestions
    }


@app.get("/debug/folder-mapping")
async def debug_folder_mapping():
    """Show current Todoist → Obsidian folder mapping"""
    root_folders = todoist.get_root_folders()
    projects = todoist.get_all_projects()
    
    mapping = []
    for p in projects:
        obsidian_path = github._get_folder_path(p.name, p.parent_name)
        mapping.append({
            "todoist_project": p.name,
            "parent": p.parent_name,
            "obsidian_path": obsidian_path
        })
    
    return {
        "root_folders": list(root_folders),
        "mapping": mapping
    }


@app.post("/test/error-log")
async def test_error_log(error_type: str = "Test Error", message: str = "This is a test error"):
    """Test endpoint to create an error log"""
    try:
        # Simulate an error with context
        raise ValueError("Simulated exception for testing")
    except Exception as e:
        file_path = log_error(
            error_type=error_type,
            error_message=message,
            context={
                "test_param": "test_value",
                "endpoint": "/test/error-log",
                "timestamp": "auto-generated"
            },
            exception=e
        )
        return {
            "status": "logged",
            "file_path": file_path
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
