"""
GitHub integration for Obsidian vault
"""
import os
import base64
from datetime import datetime
from github import Github
from summarizer import SummaryResult, ResearchResult
from logger import get_logger

logger = get_logger(__name__)



class ObsidianGitHub:
    def __init__(self, todoist_client=None):
        self.github = Github(os.getenv("GITHUB_TOKEN"))
        self.repo_name = os.getenv("GITHUB_REPO", "nydamon/obsidian")
        self.repo = self.github.get_repo(self.repo_name)
        self.todoist = todoist_client
        
        # Todoist project -> Obsidian folder mapping
        self.folder_mapping = {}  # Will be populated from Todoist
        
    def _slugify(self, text: str) -> str:
        """Convert text to filename-safe slug"""
        import re
        # Remove special chars, replace spaces with hyphens
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        return slug[:50]  # Limit length
    
    def _get_folder_path(self, project_name: str, parent_project: str = None) -> str:
        """Map Todoist project to Obsidian folder path"""
        
        # Get root folders dynamically from Todoist
        root_folders = self.todoist.get_root_folders() if self.todoist else set()
        
        # Default inbox
        if project_name.lower() == "inbox":
            return "_Inbox"
        
        # If task is in a root folder directly (no parent), use _Inbox subfolder
        if project_name.lower() in root_folders and not parent_project:
            return f"{project_name}/_Inbox"
        
        # If has parent project, it's a nested project
        if parent_project:
            return f"{parent_project}/{project_name}"
        
        # Otherwise it's a standalone project at root
        return f"Projects/{project_name}"
    
    def create_note(self, summary: SummaryResult, project_name: str, 
                    parent_project: str = None, todoist_task_id: str = None,
                    priority: int = 4) -> str:
        """Create a new note in the Obsidian vault"""
        
        folder_path = self._get_folder_path(project_name, parent_project)
        
        # Generate clean filename (no emojis - use Supercharged Links for visual indicators)
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        slug = self._slugify(summary.title)
        filename = f"{date_prefix}-{slug}.md"
        file_path = f"{folder_path}/{filename}"
        
        # Build note content
        content = self._build_note_content(summary, todoist_task_id, priority)
        
        # Create or update file in GitHub
        try:
            # Check if file exists
            self.repo.get_contents(file_path)
            # Update existing
            self.repo.update_file(
                file_path,
                f"Update note: {summary.title}",
                content,
                self.repo.get_contents(file_path).sha
            )
        except:
            # Create new
            self.repo.create_file(
                file_path,
                f"Add note: {summary.title}",
                content
            )
        
        return file_path
    
    def _build_note_content(self, summary: SummaryResult, todoist_task_id: str = None, 
                             priority: int = 4) -> str:
        """Build markdown content for the note"""
        
        # Frontmatter
        frontmatter = f"""---
source: {summary.source_url}
captured: {datetime.now().strftime("%Y-%m-%d")}
status: new
type: {summary.url_type.value}
"""
        if todoist_task_id:
            frontmatter += f"todoist_id: {todoist_task_id}\n"
        
        frontmatter += f"priority: {priority}\n"
        
        # Add extra metadata
        for key, value in summary.extra_metadata.items():
            if value:
                frontmatter += f"{key}: {value}\n"
        
        frontmatter += "---\n\n"
        
        # Title
        content = f"# 🆕 {summary.title}\n\n"

        # Embed video if present (for X+YouTube or standalone YouTube)
        video_url = summary.extra_metadata.get("video_url")
        if not video_url and summary.url_type.value == "youtube":
            video_url = summary.source_url

        if video_url:
            # Extract video ID and create embed
            video_id = None
            if 'youtu.be/' in video_url:
                video_id = video_url.split('youtu.be/')[-1].split('?')[0]
            elif 'youtube.com/watch?v=' in video_url:
                video_id = video_url.split('v=')[-1].split('&')[0]

            if video_id:
                content += f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>\n\n'

        # Summary
        content += f"## Summary\n\n{summary.summary}\n\n"
        
        # Video Stages (chapters with timestamps)
        stages = summary.extra_metadata.get("stages", [])
        if stages:
            content += "## Video Chapters\n\n"
            for stage in stages:
                content += f"- {stage}\n"
            content += "\n"

        # Key Points
        if summary.key_points:
            content += "## Key Points\n\n"
            for point in summary.key_points:
                content += f"- {point}\n"
            content += "\n"

        # Critical Notes (gotchas, limitations)
        critical_notes = summary.extra_metadata.get("critical_notes")
        if critical_notes and critical_notes != "null":
            content += f"## Critical Notes\n\n{critical_notes}\n\n"

        # Source link
        content += f"## Source\n\n[Original]({summary.source_url})\n"
        
        return frontmatter + content
    
    def create_folder(self, folder_path: str) -> bool:
        """Create a folder in the vault (via .gitkeep)"""
        try:
            gitkeep_path = f"{folder_path}/.gitkeep"
            self.repo.create_file(
                gitkeep_path,
                f"Create folder: {folder_path}",
                ""
            )
            return True
        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            return False
    
    def delete_folder(self, folder_path: str) -> bool:
        """Delete a folder (move contents to Archive)"""
        try:
            # Get all contents
            contents = self.repo.get_contents(folder_path)
            
            for item in contents:
                if item.type == "file":
                    # Move to archive
                    archive_path = f"Archive/{item.path}"
                    file_content = base64.b64decode(item.content).decode()
                    
                    # Create in archive
                    self.repo.create_file(
                        archive_path,
                        f"Archive: {item.path}",
                        file_content
                    )
                    
                    # Delete original
                    self.repo.delete_file(
                        item.path,
                        f"Move to archive: {item.path}",
                        item.sha
                    )
            
            return True
        except Exception as e:
            logger.error(f"Error deleting folder: {e}")
            return False
    
    def create_research_note(self, research: ResearchResult, project_name: str,
                              parent_project: str = None, todoist_task_id: str = None,
                              priority: int = 4) -> str:
        """Create a research note from @note tagged task"""
        
        folder_path = self._get_folder_path(project_name, parent_project)
        
        # Generate clean filename
        slug = self._slugify(research.title)
        filename = f"{slug}.md"
        file_path = f"{folder_path}/{filename}"
        
        # Build note content
        content = self._build_research_content(research, todoist_task_id, priority)
        
        # Create or update file in GitHub
        try:
            self.repo.get_contents(file_path)
            self.repo.update_file(
                file_path,
                f"Update research: {research.title}",
                content,
                self.repo.get_contents(file_path).sha
            )
        except:
            self.repo.create_file(
                file_path,
                f"Add research: {research.title}",
                content
            )
        
        return file_path
    
    def _build_research_content(self, research: ResearchResult, todoist_task_id: str = None,
                                 priority: int = 4) -> str:
        """Build markdown content for research note"""
        
        frontmatter = f"""---
captured: {datetime.now().strftime("%Y-%m-%d")}
status: new
type: research
priority: {priority}
"""
        if todoist_task_id:
            frontmatter += f"todoist_id: {todoist_task_id}\n"
        
        frontmatter += "---\n\n"
        
        # Title
        content = f"# {research.title}\n\n"
        
        # Overview
        content += f"## Overview\n\n{research.summary}\n\n"
        
        # Key Points
        if research.key_points:
            content += "## Key Points\n\n"
            for point in research.key_points:
                content += f"- {point}\n"
            content += "\n"
        
        # Research Suggestions
        if research.suggestions:
            content += "## To Explore\n\n"
            for suggestion in research.suggestions:
                content += f"- [ ] {suggestion}\n"
            content += "\n"
        
        # Notes section for manual additions
        content += "## Notes\n\n"
        
        return frontmatter + content

    def archive_note(self, file_path: str) -> bool:
        """Move a note to Archive folder"""
        try:
            content = self.repo.get_contents(file_path)
            file_content = base64.b64decode(content.content).decode()
            
            # Update frontmatter status
            file_content = file_content.replace("status: new", "status: archived")
            
            filename = file_path.split("/")[-1]
            archive_path = f"Archive/{filename}"
            
            # Create in archive
            self.repo.create_file(
                archive_path,
                f"Archive note: {file_path}",
                file_content
            )
            
            # Delete original
            self.repo.delete_file(
                file_path,
                f"Archived: {file_path}",
                content.sha
            )
            
            return True
        except Exception as e:
            logger.error(f"Error archiving note: {e}")
            return False
