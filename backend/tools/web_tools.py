from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ddgs import DDGS
from ddgs.exceptions import DDGSException

DEFAULT_WEB_RESULTS = 5
MAX_WEB_RESULTS = 8
MAX_QUERY_CHARACTERS = 500
MAX_TITLE_CHARACTERS = 300
MAX_SNIPPET_CHARACTERS = 1200
MAX_URL_CHARACTERS = 2000


def web_search(
    query: str,
    max_results: int = DEFAULT_WEB_RESULTS,
) -> dict[str, Any]:
    """Search the public web and return bounded titles, URLs, and snippets.

    The query is sent to external search providers. Callers must never include
    secrets, credentials, private source code, or other sensitive workspace
    content in it.
    """

    clean_query = query.strip()
    if not clean_query:
        raise ValueError("Web search requires a non-empty query")
    if len(clean_query) > MAX_QUERY_CHARACTERS:
        raise ValueError(
            f"Web search queries may not exceed {MAX_QUERY_CHARACTERS} characters"
        )
    if (
        not isinstance(max_results, int)
        or isinstance(max_results, bool)
        or not 1 <= max_results <= MAX_WEB_RESULTS
    ):
        raise ValueError(
            f"max_results must be an integer between 1 and {MAX_WEB_RESULTS}"
        )

    try:
        raw_results = DDGS(timeout=10).text(
            clean_query,
            max_results=max_results,
            backend="auto",
        )
    except DDGSException as error:
        raise RuntimeError(f"Web search failed: {error}") from error
    except OSError as error:
        raise RuntimeError(f"Web search connection failed: {error}") from error

    results: list[dict[str, str]] = []
    for raw_result in raw_results or []:
        if not isinstance(raw_result, dict):
            continue

        url = _bounded_text(raw_result.get("href"), MAX_URL_CHARACTERS)
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            continue

        results.append(
            {
                "title": _bounded_text(
                    raw_result.get("title"),
                    MAX_TITLE_CHARACTERS,
                ),
                "url": url,
                "snippet": _bounded_text(
                    raw_result.get("body"),
                    MAX_SNIPPET_CHARACTERS,
                ),
            }
        )
        if len(results) >= max_results:
            break

    return {
        "query": clean_query,
        "result_count": len(results),
        "results": results,
    }


def _bounded_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"
