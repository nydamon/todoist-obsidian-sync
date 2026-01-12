"""
Tests for github_sync.py - Slugify and folder path mapping
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSlugify:
    """Tests for _slugify method"""

    @pytest.fixture
    def github_sync(self, mock_todoist_client):
        """Create ObsidianGitHub instance with mocked dependencies"""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token", "GITHUB_REPO": "test/repo"}):
            with patch("github_sync.Github"):
                from github_sync import ObsidianGitHub
                sync = ObsidianGitHub(todoist_client=mock_todoist_client)
                return sync

    def test_slugify_basic(self, github_sync):
        """Basic text should convert to lowercase hyphenated slug"""
        assert github_sync._slugify("Hello World") == "hello-world"

    def test_slugify_special_chars(self, github_sync):
        """Special characters should be removed"""
        assert github_sync._slugify("What's New?") == "whats-new"
        assert github_sync._slugify("Test: A Guide!") == "test-a-guide"

    def test_slugify_max_length(self, github_sync):
        """Slug should be truncated to 50 characters"""
        long_title = "This is a very long title that exceeds fifty characters easily"
        slug = github_sync._slugify(long_title)
        assert len(slug) <= 50

    def test_slugify_multiple_spaces(self, github_sync):
        """Multiple spaces should become single hyphen"""
        assert github_sync._slugify("Too   Many    Spaces") == "too-many-spaces"

    def test_slugify_trailing_hyphens(self, github_sync):
        """Trailing hyphens should be stripped"""
        assert github_sync._slugify("Ends With Punctuation!") == "ends-with-punctuation"


class TestFolderPathMapping:
    """Tests for _get_folder_path method"""

    @pytest.fixture
    def github_sync(self, mock_todoist_client):
        """Create ObsidianGitHub instance with mocked dependencies"""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token", "GITHUB_REPO": "test/repo"}):
            with patch("github_sync.Github"):
                from github_sync import ObsidianGitHub
                sync = ObsidianGitHub(todoist_client=mock_todoist_client)
                return sync

    def test_folder_path_inbox(self, github_sync):
        """Inbox should map to _Inbox"""
        assert github_sync._get_folder_path("Inbox") == "_Inbox"
        assert github_sync._get_folder_path("inbox") == "_Inbox"  # Case insensitive

    def test_folder_path_root_folder(self, github_sync):
        """Root folder should get _Inbox subfolder"""
        # "personal" is in mock root_folders
        path = github_sync._get_folder_path("personal")
        assert path == "personal/_Inbox"

    def test_folder_path_nested(self, github_sync):
        """Nested project with parent should use parent/child format"""
        path = github_sync._get_folder_path("Subproject", parent_project="ParentProject")
        assert path == "ParentProject/Subproject"

    def test_folder_path_default(self, github_sync):
        """Unknown project should go to Projects folder"""
        path = github_sync._get_folder_path("SomeRandomProject")
        assert path == "Projects/SomeRandomProject"
