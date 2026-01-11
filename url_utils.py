"""
URL detection and routing utilities
"""
import re
from enum import Enum


class URLType(Enum):
    X_TWITTER = "x-thread"
    YOUTUBE = "youtube"
    ARTICLE = "article"


def detect_url_type(url: str) -> URLType:
    """Detect the type of URL for model routing"""
    
    # X/Twitter patterns
    x_patterns = [
        r'https?://(www\.)?(twitter\.com|x\.com)/\w+/status/\d+',
        r'https?://(www\.)?(twitter\.com|x\.com)/\w+',
    ]
    
    # YouTube patterns
    youtube_patterns = [
        r'https?://(www\.)?(youtube\.com|youtu\.be)/',
        r'https?://m\.youtube\.com/',
    ]
    
    for pattern in x_patterns:
        if re.match(pattern, url):
            return URLType.X_TWITTER
    
    for pattern in youtube_patterns:
        if re.match(pattern, url):
            return URLType.YOUTUBE
    
    return URLType.ARTICLE


def extract_url_from_text(text: str) -> str | None:
    """Extract first URL from text"""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None
