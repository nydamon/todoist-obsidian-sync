"""
Tests for url_utils.py - URL detection and extraction
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from url_utils import URLType, detect_url_type, extract_url_from_text


class TestDetectURLType:
    """Tests for detect_url_type function"""

    def test_detect_x_twitter_status_url(self):
        """twitter.com/*/status/* should return X_TWITTER"""
        url = "https://twitter.com/naval/status/1234567890"
        assert detect_url_type(url) == URLType.X_TWITTER

    def test_detect_x_com_status_url(self):
        """x.com/*/status/* should return X_TWITTER"""
        url = "https://x.com/elonmusk/status/9876543210"
        assert detect_url_type(url) == URLType.X_TWITTER

    def test_detect_x_twitter_profile_url(self):
        """twitter.com profile URL should return X_TWITTER"""
        url = "https://twitter.com/paulg"
        assert detect_url_type(url) == URLType.X_TWITTER

    def test_detect_youtube_watch_url(self):
        """youtube.com/watch?v= should return YOUTUBE"""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert detect_url_type(url) == URLType.YOUTUBE

    def test_detect_youtube_short_url(self):
        """youtu.be/* should return YOUTUBE"""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert detect_url_type(url) == URLType.YOUTUBE

    def test_detect_youtube_mobile_url(self):
        """m.youtube.com/* should return YOUTUBE"""
        url = "https://m.youtube.com/watch?v=abc123"
        assert detect_url_type(url) == URLType.YOUTUBE

    def test_detect_article_fallback(self):
        """Non-matching URLs should return ARTICLE"""
        urls = [
            "https://www.paulgraham.com/greatwork.html",
            "https://medium.com/@user/article-title",
            "https://substack.com/post/123",
            "https://news.ycombinator.com/item?id=123",
        ]
        for url in urls:
            assert detect_url_type(url) == URLType.ARTICLE


class TestExtractURLFromText:
    """Tests for extract_url_from_text function"""

    def test_extract_url_from_text_simple(self):
        """Extract URL from simple text"""
        text = "Check out this article: https://example.com/article"
        assert extract_url_from_text(text) == "https://example.com/article"

    def test_extract_first_url_only(self):
        """Should return only the first URL when multiple present"""
        text = "First https://first.com then https://second.com"
        assert extract_url_from_text(text) == "https://first.com"

    def test_extract_url_none(self):
        """Should return None when no URL present"""
        text = "This text has no URLs in it at all"
        assert extract_url_from_text(text) is None

    def test_extract_url_with_query_params(self):
        """Should extract URL with query parameters"""
        text = "Watch this: https://youtube.com/watch?v=abc123&t=60"
        assert extract_url_from_text(text) == "https://youtube.com/watch?v=abc123&t=60"

    def test_extract_http_url(self):
        """Should extract http:// URLs (not just https)"""
        text = "Old link: http://example.com/page"
        assert extract_url_from_text(text) == "http://example.com/page"
