"""
Tests for summarizer.py - JSON parsing, link validation, folder context
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from summarizer import AISummarizer


class TestParseJSONResponse:
    """Tests for _parse_json_response method"""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer instance (no API keys needed for parsing tests)"""
        return AISummarizer()

    def test_parse_json_valid(self, summarizer, sample_json_response):
        """Valid JSON should parse correctly"""
        result = summarizer._parse_json_response(sample_json_response)

        assert result["title"] == "Test Article Title"
        assert "test summary" in result["summary"]
        assert len(result["key_points"]) == 3
        assert result["author"] == "Test Author"

    def test_parse_json_markdown_wrapped(self, summarizer, sample_json_markdown_wrapped):
        """JSON wrapped in markdown code block should parse"""
        result = summarizer._parse_json_response(sample_json_markdown_wrapped)

        assert result["title"] == "Wrapped JSON Title"
        assert len(result["key_points"]) == 2

    def test_parse_json_regex_fallback(self, summarizer, sample_malformed_json):
        """Malformed response should still extract JSON via regex"""
        result = summarizer._parse_json_response(sample_malformed_json)

        assert result["title"] == "Extractable Title"
        assert "can still be extracted" in result["summary"]

    def test_parse_json_invalid_returns_empty(self, summarizer):
        """Completely invalid JSON should return empty dict"""
        invalid = "This has no JSON at all, just plain text."
        result = summarizer._parse_json_response(invalid)

        assert result == {}


class TestValidateLinks:
    """Tests for _validate_links method"""

    @pytest.fixture
    def summarizer(self):
        return AISummarizer()

    def test_validate_links_http_https(self, summarizer):
        """Valid http/https links should be preserved"""
        key_points = [
            "Point with http link [->](http://example.com)",
            "Point with https link [->](https://secure.example.com/page)",
        ]
        result = summarizer._validate_links(key_points)

        assert "[->](http://example.com)" in result[0]
        assert "[->](https://secure.example.com/page)" in result[1]

    def test_validate_links_remove_invalid(self, summarizer):
        """Invalid protocol links should be removed"""
        key_points = [
            "Bad link [click](javascript:alert('xss'))",
            "Data link [img](data:image/png;base64,xxx)",
        ]
        result = summarizer._validate_links(key_points)

        # Links should be removed, text preserved
        assert "javascript:" not in result[0]
        assert "data:" not in result[1]
        assert "Bad link" in result[0]  # Text part preserved

    def test_validate_links_relative_paths(self, summarizer):
        """Relative paths and anchors should be preserved"""
        key_points = [
            "Relative link [page](/other/page)",
            "Anchor link [section](#heading)",
            "Mailto link [email](mailto:test@example.com)",
        ]
        result = summarizer._validate_links(key_points)

        assert "[page](/other/page)" in result[0]
        assert "[section](#heading)" in result[1]
        assert "[email](mailto:test@example.com)" in result[2]


class TestFolderContext:
    """Tests for _get_folder_context method"""

    @pytest.fixture
    def summarizer(self):
        return AISummarizer()

    def test_folder_context_travel(self, summarizer):
        """Travel project should return travel context"""
        context = summarizer._get_folder_context("Travel")
        assert "travel destination" in context.lower()

    def test_folder_context_learning(self, summarizer):
        """Learning project should return learning context"""
        context = summarizer._get_folder_context("Learning")
        assert "learning topic" in context.lower()

    def test_folder_context_parent_fallback(self, summarizer):
        """Should fall back to parent project context"""
        context = summarizer._get_folder_context("Specific Trip", "Travel")
        assert "travel destination" in context.lower()

    def test_folder_context_default(self, summarizer):
        """Unknown project should return generic context"""
        context = summarizer._get_folder_context("Random Project")
        assert "helpful overview" in context.lower()
