"""
Error logging to Obsidian vault
"""
import os
import traceback
from datetime import datetime
from github import Github


class ErrorLogger:
    def __init__(self):
        self.github = Github(os.getenv("GITHUB_TOKEN"))
        self.repo_name = os.getenv("GITHUB_REPO", "nydamon/obsidian")
        self.repo = self.github.get_repo(self.repo_name)
        self.error_folder = "_System/Error-Logs"
    
    def log_error(self, error_type: str, error_message: str, 
                  context: dict = None, exception: Exception = None) -> str:
        """Create an error note in the vault"""
        
        timestamp = datetime.now()
        date_str = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%H-%M-%S")
        
        # Generate filename
        slug = error_type.lower().replace(" ", "-").replace("_", "-")[:30]
        filename = f"{date_str}-{time_str}-{slug}.md"
        file_path = f"{self.error_folder}/{filename}"
        
        # Build content
        content = self._build_error_content(
            error_type=error_type,
            error_message=error_message,
            timestamp=timestamp,
            context=context,
            exception=exception
        )
        
        # Create file in GitHub
        try:
            self.repo.create_file(
                file_path,
                f"Error log: {error_type}",
                content
            )
            print(f"Error logged: {file_path}")
            return file_path
        except Exception as e:
            # Fallback to console if GitHub fails
            print(f"FAILED TO LOG ERROR TO GITHUB: {e}")
            print(f"Original error: {error_type} - {error_message}")
            return None
    
    def _build_error_content(self, error_type: str, error_message: str,
                              timestamp: datetime, context: dict = None,
                              exception: Exception = None) -> str:
        """Build markdown content for error note"""
        
        frontmatter = f"""---
type: error-log
error_type: {error_type}
timestamp: {timestamp.isoformat()}
status: unresolved
---

"""
        
        content = f"# ❌ {error_type}\n\n"
        content += f"**Time:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Error message
        content += f"## Error Message\n\n```\n{error_message}\n```\n\n"
        
        # Context
        if context:
            content += "## Context\n\n"
            for key, value in context.items():
                content += f"- **{key}:** `{value}`\n"
            content += "\n"
        
        # Stack trace
        if exception:
            tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
            content += "## Stack Trace\n\n```python\n"
            content += "".join(tb)
            content += "```\n\n"
        
        # Resolution section
        content += "## Resolution\n\n- [ ] Investigated\n- [ ] Fixed\n- [ ] Tested\n\n"
        content += "## Notes\n\n"
        
        return frontmatter + content


# Singleton instance
_logger = None

def get_error_logger() -> ErrorLogger:
    global _logger
    if _logger is None:
        _logger = ErrorLogger()
    return _logger


def log_error(error_type: str, error_message: str, 
              context: dict = None, exception: Exception = None) -> str:
    """Convenience function to log errors"""
    return get_error_logger().log_error(error_type, error_message, context, exception)
