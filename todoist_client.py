"""
Todoist API integration
"""
import os
from typing import Optional, List
from todoist_api_python.api import TodoistAPI
from dataclasses import dataclass
from logger import get_logger

logger = get_logger(__name__)


@dataclass
class TodoistProject:
    id: str
    name: str
    parent_id: Optional[str] = None
    parent_name: Optional[str] = None


@dataclass 
class TodoistTask:
    id: str
    content: str
    description: str
    project_id: str
    project_name: str
    parent_project_name: Optional[str] = None
    priority: int = 4  # Todoist: 1=urgent, 4=default
    labels: List[str] = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = []


class TodoistClient:
    def __init__(self):
        self.api = TodoistAPI(os.getenv("TODOIST_API_KEY"))
        self._project_cache = {}
        self._root_folders = set()  # Projects that have children
        self._refresh_projects()
    
    def _refresh_projects(self):
        """Cache all projects with their hierarchy"""
        # Handle paginated results from Todoist API v3
        all_projects = []
        for page in self.api.get_projects():
            if isinstance(page, list):
                all_projects.extend(page)
            else:
                all_projects.append(page)

        # First pass: cache all projects
        for p in all_projects:
            self._project_cache[p.id] = {
                "name": p.name,
                "parent_id": p.parent_id
            }
        
        # Second pass: resolve parent names and identify root folders
        self._root_folders = set()
        for pid, pdata in self._project_cache.items():
            if pdata["parent_id"]:
                parent = self._project_cache.get(pdata["parent_id"])
                pdata["parent_name"] = parent["name"] if parent else None
                # Mark parent as a root folder (has children)
                if parent:
                    self._root_folders.add(parent["name"].lower())
            else:
                pdata["parent_name"] = None
    
    def get_root_folders(self) -> set:
        """Get set of project names that have children (root folders)"""
        return self._root_folders.copy()
    
    def get_project(self, project_id: str) -> Optional[TodoistProject]:
        """Get project by ID"""
        if project_id not in self._project_cache:
            self._refresh_projects()
        
        pdata = self._project_cache.get(project_id)
        if not pdata:
            return None
        
        return TodoistProject(
            id=project_id,
            name=pdata["name"],
            parent_id=pdata.get("parent_id"),
            parent_name=pdata.get("parent_name")
        )
    
    def get_all_projects(self) -> List[TodoistProject]:
        """Get all projects"""
        self._refresh_projects()
        return [
            TodoistProject(
                id=pid,
                name=pdata["name"],
                parent_id=pdata.get("parent_id"),
                parent_name=pdata.get("parent_name")
            )
            for pid, pdata in self._project_cache.items()
        ]
    
    def get_task(self, task_id: str) -> Optional[TodoistTask]:
        """Get task by ID"""
        try:
            task = self.api.get_task(task_id)
            project = self.get_project(task.project_id)
            
            return TodoistTask(
                id=task.id,
                content=task.content,
                description=task.description or "",
                project_id=task.project_id,
                project_name=project.name if project else "Inbox",
                parent_project_name=project.parent_name if project else None,
                priority=task.priority,  # 1=urgent, 4=default
                labels=task.labels
            )
        except Exception as e:
            logger.error(f"Error getting task: {e}")
            return None
    
    def complete_task(self, task_id: str) -> bool:
        """Mark task as complete"""
        try:
            self.api.close_task(task_id)
            return True
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            return False
    
    def create_project(self, name: str, parent_id: str = None) -> Optional[str]:
        """Create a new project"""
        try:
            project = self.api.add_project(name=name, parent_id=parent_id)
            self._refresh_projects()
            return project.id
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return None
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project"""
        try:
            self.api.delete_project(project_id)
            self._refresh_projects()
            return True
        except Exception as e:
            logger.error(f"Error deleting project: {e}")
            return False
