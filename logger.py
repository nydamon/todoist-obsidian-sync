"""
Centralized logging configuration for Todoist-Obsidian Sync
"""
import logging
import os
import sys

# Get log level from environment, default to INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Validate log level
if hasattr(logging, LOG_LEVEL):
    level = getattr(logging, LOG_LEVEL)
else:
    level = logging.INFO
    # Can't use logger here (not configured yet), so use print
    print(f"Warning: Invalid LOG_LEVEL '{LOG_LEVEL}', defaulting to INFO", file=sys.stderr)

# Configure root logger
logging.basicConfig(
    level=level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)
