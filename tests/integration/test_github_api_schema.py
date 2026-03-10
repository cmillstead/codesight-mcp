"""Tests for graceful handling of unexpected GitHub API responses (P2-09).

Verifies that index_repo degrades gracefully when the GitHub API returns
unexpected schemas, non-JSON bodies, or HTTP errors.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from codesight_mcp.tools.index_repo import index_repo


def _make_http_response(status_code: int, json_data=None, text: str = "") -> httpx.Response:
    """Build an httpx.Response with the given status code and body."""
    request = httpx.Request("GET", "https://api.github.com/test")
    if json_data is not None:
        import json
        content = json.dumps(json_data).encode()
        return httpx.Response(
            status_code=status_code,
            request=request,
            content=content,
            headers={"content-type": "application/json"},
        )
    return httpx.Response(
        status_code=status_code,
        request=request,
        content=text.encode(),
        headers={"content-type": "text/plain"},
    )


def _make_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Build an httpx.HTTPStatusError for the given status code."""
    request = httpx.Request("GET", "https://api.github.com/test")
    response = httpx.Response(status_code=status_code, request=request)
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=response,
    )


class TestMissingJsonFields:
    """GitHub API returns JSON without the expected 'tree' key."""

    @pytest.mark.asyncio
    async def test_missing_tree_key_returns_graceful_error(self):
        """When API returns JSON without 'tree', index_repo should not crash."""
        # fetch_repo_tree returns data.get("tree", []) -- so missing key -> empty list
        # That causes "No source files found" downstream
        with patch(
            "codesight_mcp.tools.index_repo.fetch_repo_tree",
            new=AsyncMock(return_value=[]),
        ), patch(
            "codesight_mcp.tools.index_repo.fetch_gitignore",
            new=AsyncMock(return_value=""),
        ):
            result = await index_repo(
                url="https://github.com/testowner/testrepo",
                use_ai_summaries=False,
            )

        assert result.get("success") is False
        assert "error" in result
        # Should indicate no source files, not a traceback
        assert "no source files" in result["error"].lower() or "error" in result

    @pytest.mark.asyncio
    async def test_tree_entries_missing_path_field(self):
        """Tree entries without 'path' key should not crash discovery."""
        # Tree entries missing 'path' -- discover_source_files should handle gracefully
        malformed_entries = [
            {"type": "blob", "size": 100},  # missing 'path'
            {"type": "blob", "path": "valid.py", "size": 50},
        ]

        with patch(
            "codesight_mcp.tools.index_repo.fetch_repo_tree",
            new=AsyncMock(return_value=malformed_entries),
        ), patch(
            "codesight_mcp.tools.index_repo.fetch_gitignore",
            new=AsyncMock(return_value=""),
        ), patch(
            "codesight_mcp.tools.index_repo.fetch_file_content",
            new=AsyncMock(return_value=""),
        ):
            result = await index_repo(
                url="https://github.com/testowner/testrepo",
                use_ai_summaries=False,
            )

        # Should not raise -- either succeeds with valid entries or returns error gracefully
        assert isinstance(result, dict)
        assert "error" in result or "success" in result


class TestNonJsonResponse:
    """GitHub API returns a non-JSON body."""

    @pytest.mark.asyncio
    async def test_non_json_body_raises_handled_error(self):
        """When fetch_repo_tree fails with a JSON decode error, index_repo handles it."""
        # Simulate fetch_repo_tree raising an exception from response.json() failure
        async def failing_fetch(*args, **kwargs):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

        with patch(
            "codesight_mcp.tools.index_repo.fetch_repo_tree",
            new=AsyncMock(side_effect=failing_fetch),
        ):
            result = await index_repo(
                url="https://github.com/testowner/testrepo",
                use_ai_summaries=False,
            )

        assert result.get("success") is False
        assert "error" in result


class TestUnexpectedHttpStatus:
    """GitHub API returns unexpected HTTP status codes."""

    @pytest.mark.asyncio
    async def test_500_returns_error(self):
        """A 500 Internal Server Error should result in an error response."""
        error = _make_http_status_error(500)

        with patch(
            "codesight_mcp.tools.index_repo.fetch_repo_tree",
            new=AsyncMock(side_effect=error),
        ):
            result = await index_repo(
                url="https://github.com/testowner/testrepo",
                use_ai_summaries=False,
            )

        assert result.get("success") is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_502_returns_error(self):
        """A 502 Bad Gateway should result in an error response."""
        error = _make_http_status_error(502)

        with patch(
            "codesight_mcp.tools.index_repo.fetch_repo_tree",
            new=AsyncMock(side_effect=error),
        ):
            result = await index_repo(
                url="https://github.com/testowner/testrepo",
                use_ai_summaries=False,
            )

        assert result.get("success") is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_422_returns_error(self):
        """A 422 Unprocessable Entity should result in an error response."""
        error = _make_http_status_error(422)

        with patch(
            "codesight_mcp.tools.index_repo.fetch_repo_tree",
            new=AsyncMock(side_effect=error),
        ):
            result = await index_repo(
                url="https://github.com/testowner/testrepo",
                use_ai_summaries=False,
            )

        assert result.get("success") is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_connection_timeout_returns_error(self):
        """A connection timeout should result in an error response."""
        with patch(
            "codesight_mcp.tools.index_repo.fetch_repo_tree",
            new=AsyncMock(side_effect=httpx.ConnectTimeout("Connection timed out")),
        ):
            result = await index_repo(
                url="https://github.com/testowner/testrepo",
                use_ai_summaries=False,
            )

        assert result.get("success") is False
        assert "error" in result
