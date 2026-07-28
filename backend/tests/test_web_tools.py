from unittest.mock import Mock, patch

import pytest

from tools.web_tools import web_search


def test_web_search_returns_bounded_public_results():
    client = Mock()
    client.text.return_value = [
        {
            "title": "Pydantic AI",
            "href": "https://ai.pydantic.dev/",
            "body": "A Python agent framework.",
        },
        {
            "title": "Unsafe result",
            "href": "javascript:alert(1)",
            "body": "Must be discarded.",
        },
    ]

    with patch("tools.web_tools.DDGS", return_value=client):
        result = web_search("  Pydantic AI docs  ", max_results=5)

    client.text.assert_called_once_with(
        "Pydantic AI docs",
        max_results=5,
        backend="auto",
    )
    assert result == {
        "query": "Pydantic AI docs",
        "result_count": 1,
        "results": [
            {
                "title": "Pydantic AI",
                "url": "https://ai.pydantic.dev/",
                "snippet": "A Python agent framework.",
            }
        ],
    }


@pytest.mark.parametrize("max_results", [0, 9, True])
def test_web_search_rejects_unbounded_result_counts(max_results):
    with pytest.raises(ValueError, match="between 1 and 8"):
        web_search("safe query", max_results=max_results)


def test_web_search_rejects_empty_or_oversized_queries():
    with pytest.raises(ValueError, match="non-empty"):
        web_search(" ")
    with pytest.raises(ValueError, match="may not exceed"):
        web_search("x" * 501)
