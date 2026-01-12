"""
URL detection and routing utilities
"""
import re
from enum import Enum
from typing import Optional


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


def extract_url_from_text(text: str) -> Optional[str]:
    """Extract first URL from text, stripping trailing punctuation"""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    match = re.search(url_pattern, text)
    if not match:
        return None
    url = match.group(0)
    # Strip trailing punctuation that commonly wraps URLs in text
    # e.g., (https://example.com) or https://example.com,
    url = url.rstrip('.,;:!?)\'\"')
    return url
