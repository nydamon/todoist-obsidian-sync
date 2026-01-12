"""
Tests for error_logger.py - Error note generation
"""
import pytest
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestErrorLoggerDatetimeFormat:
    """Tests for datetime formatting in error logs"""

    def test_datetime_format_compact(self):
        """Datetime should use YY-MM-DD-HHMM format"""
        timestamp = datetime(2026, 1, 12, 14, 30)
        datetime_str = timestamp.strftime("%y-%m-%d-%H%M")
        assert datetime_str == "26-01-12-1430"

    def test_datetime_format_midnight(self):
        """Midnight should format correctly"""
        timestamp = datetime(2026, 12, 31, 0, 0)
        datetime_str = timestamp.strftime("%y-%m-%d-%H%M")
        assert datetime_str == "26-12-31-0000"


class TestErrorContentStructure:
    """Tests for _build_error_content method"""

    @pytest.fixture
    def error_logger(self):
        """Create ErrorLogger instance with mocked GitHub"""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token", "GITHUB_REPO": "test/repo"}):
            with patch("error_logger.Github"):
                from error_logger import ErrorLogger
                return ErrorLogger()

    def test_error_content_has_frontmatter(self, error_logger):
        """Error content should include YAML frontmatter"""
        content = error_logger._build_error_content(
            error_type="Test Error",
            error_message="Something went wrong",
            timestamp=datetime.now()
        )

        assert content.startswith("---")
        assert "type: error-log" in content
        assert "error_type: Test Error" in content
        assert "status: unresolved" in content

    def test_error_content_has_message(self, error_logger):
        """Error content should include the error message"""
        content = error_logger._build_error_content(
            error_type="Test Error",
            error_message="Something went wrong",
            timestamp=datetime.now()
        )

        assert "## Error Message" in content
        assert "Something went wrong" in content

    def test_error_content_with_context(self, error_logger):
        """Error content should include context when provided"""
        context = {"url": "https://example.com", "task_id": "12345"}
        content = error_logger._build_error_content(
            error_type="Test Error",
            error_message="Error occurred",
            timestamp=datetime.now(),
            context=context
        )

        assert "## Context" in content
        assert "https://example.com" in content
        assert "12345" in content

    def test_error_content_with_exception(self, error_logger):
        """Error content should include stack trace when exception provided"""
        try:
            raise ValueError("Test exception for stack trace")
        except ValueError as e:
            content = error_logger._build_error_content(
                error_type="Test Error",
                error_message="Error occurred",
                timestamp=datetime.now(),
                exception=e
            )

        assert "## Stack Trace" in content
        assert "ValueError" in content
        assert "Test exception for stack trace" in content

    def test_error_content_has_resolution_checklist(self, error_logger):
        """Error content should include resolution checklist"""
        content = error_logger._build_error_content(
            error_type="Test Error",
            error_message="Error occurred",
            timestamp=datetime.now()
        )

        assert "## Resolution" in content
        assert "- [ ] Investigated" in content
        assert "- [ ] Fixed" in content
        assert "- [ ] Tested" in content
