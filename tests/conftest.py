"""
Shared fixtures for pytest tests
"""
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_todoist_client():
    """Mock Todoist client for folder mapping tests"""
    client = MagicMock()
    client.get_root_folders.return_value = {"personal", "work", "leisure"}
    return client


@pytest.fixture
def mock_github_client():
    """Mock GitHub client for sync tests"""
    client = MagicMock()
    client.get_repo.return_value = MagicMock()
    return client


@pytest.fixture
def sample_json_response():
    """Valid summarization JSON response"""
    return '''{
    "title": "Test Article Title",
    "summary": "This is a test summary of the article content.",
    "key_points": [
        "First key point",
        "Second key point with link [->](https://example.com)",
        "Third key point"
    ],
    "author": "Test Author",
    "publication": "Test Publication"
}'''


@pytest.fixture
def sample_json_markdown_wrapped():
    """JSON wrapped in markdown code block"""
    return '''Here is the analysis:

```json
{
    "title": "Wrapped JSON Title",
    "summary": "Summary wrapped in markdown.",
    "key_points": ["Point one", "Point two"]
}
```

That concludes the analysis.'''


@pytest.fixture
def sample_malformed_json():
    """Malformed JSON with extractable content"""
    return '''I'll analyze this article:

The title is "Malformed Response"
{
    "title": "Extractable Title",
    "summary": "This can still be extracted.",
    "key_points": ["Point A", "Point B"]
}

End of response.'''
