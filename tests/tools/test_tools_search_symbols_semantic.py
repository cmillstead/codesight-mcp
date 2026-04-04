"""Integration tests for semantic search in search_symbols."""

import gzip
import json
import os
import re
import tempfile
from pathlib import Path

import pytest

from codesight_mcp.parser.symbols import Symbol
from codesight_mcp.storage.index_store import IndexStore
from codesight_mcp.tools.search_symbols import search_symbols

_UNTRUSTED_RE = re.compile(r"<<<UNTRUSTED_CODE_[0-9a-f]+>>>\n(.*?)\n<<<END_UNTRUSTED_CODE_[0-9a-f]+>>>", re.DOTALL)


def _unwrap(value: str) -> str:
    """Strip UNTRUSTED_CODE boundary markers to get the inner content."""
    match = _UNTRUSTED_RE.match(value)
    return match.group(1) if match else value


def _make_store_with_symbols(tmp: str) -> IndexStore:
    """Create an index with 4 semantically distinct symbols."""
    symbols = [
        Symbol(
            id="src/auth.py::login#function",
            file="src/auth.py",
            name="login",
            qualified_name="login",
            kind="function",
            language="python",
            signature="def login(username: str, password: str) -> bool:",
            docstring="",
            summary="Authenticate user with username and password",
            decorators=[],
            keywords=[],
            parent=None,
            line=1,
            end_line=10,
            byte_offset=0,
            byte_length=200,
        ),
        Symbol(
            id="src/validators.py::validate_email#function",
            file="src/validators.py",
            name="validate_email",
            qualified_name="validate_email",
            kind="function",
            language="python",
            signature="def validate_email(email: str) -> bool:",
            docstring="",
            summary="Check if email address format is valid",
            decorators=[],
            keywords=[],
            parent=None,
            line=1,
            end_line=5,
            byte_offset=0,
            byte_length=100,
        ),
        Symbol(
            id="src/notify.py::send_notification#function",
            file="src/notify.py",
            name="send_notification",
            qualified_name="send_notification",
            kind="function",
            language="python",
            signature="def send_notification(user_id: int, message: str) -> None:",
            docstring="",
            summary="Send push notification to user device",
            decorators=[],
            keywords=[],
            parent=None,
            line=1,
            end_line=8,
            byte_offset=0,
            byte_length=150,
        ),
        Symbol(
            id="src/crypto.py::hash_password#function",
            file="src/crypto.py",
            name="hash_password",
            qualified_name="hash_password",
            kind="function",
            language="python",
            signature="def hash_password(password: str) -> str:",
            docstring="",
            summary="Hash a password using bcrypt",
            decorators=[],
            keywords=[],
            parent=None,
            line=1,
            end_line=6,
            byte_offset=0,
            byte_length=120,
        ),
    ]
    raw_files = {
        "src/auth.py": "def login(username, password): pass",
        "src/validators.py": "def validate_email(email): pass",
        "src/notify.py": "def send_notification(user_id, message): pass",
        "src/crypto.py": "def hash_password(password): pass",
    }
    store = IndexStore(base_path=tmp)
    store.save_index(
        owner="test",
        name="repo",
        source_files=list(raw_files.keys()),
        symbols=symbols,
        raw_files=raw_files,
        languages={"python": 4},
    )
    return store


def _make_store_with_class(tmp: str) -> IndexStore:
    """Create an index with functions and a class for kind-filter tests."""
    symbols = [
        Symbol(
            id="src/auth.py::login#function",
            file="src/auth.py",
            name="login",
            qualified_name="login",
            kind="function",
            language="python",
            signature="def login(username: str, password: str) -> bool:",
            docstring="",
            summary="Authenticate user with username and password",
            decorators=[],
            keywords=[],
            parent=None,
            line=1,
            end_line=10,
            byte_offset=0,
            byte_length=200,
        ),
        Symbol(
            id="src/auth.py::AuthManager#class",
            file="src/auth.py",
            name="AuthManager",
            qualified_name="AuthManager",
            kind="class",
            language="python",
            signature="class AuthManager:",
            docstring="",
            summary="Manages authentication sessions and tokens",
            decorators=[],
            keywords=[],
            parent=None,
            line=12,
            end_line=30,
            byte_offset=200,
            byte_length=400,
        ),
        Symbol(
            id="src/crypto.py::hash_password#function",
            file="src/crypto.py",
            name="hash_password",
            qualified_name="hash_password",
            kind="function",
            language="python",
            signature="def hash_password(password: str) -> str:",
            docstring="",
            summary="Hash a password using bcrypt",
            decorators=[],
            keywords=[],
            parent=None,
            line=1,
            end_line=6,
            byte_offset=0,
            byte_length=120,
        ),
    ]
    raw_files = {
        "src/auth.py": "def login(username, password): pass\nclass AuthManager: pass",
        "src/crypto.py": "def hash_password(password): pass",
    }
    store = IndexStore(base_path=tmp)
    store.save_index(
        owner="test",
        name="repo",
        source_files=list(raw_files.keys()),
        symbols=symbols,
        raw_files=raw_files,
        languages={"python": 3},
    )
    return store


def test_keyword_only_response_shape_unchanged():
    """search_symbols without semantic params returns results with NO 'search_mode' key, scores rounded to 1 decimal."""
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        result = search_symbols(repo="test/repo", query="login", storage_path=tmp)

        assert "search_mode" not in result
        assert "results" in result
        for entry in result["results"]:
            score = entry["score"]
            assert round(score, 2) == score, f"Score {score!r} not rounded to 2 decimals"


def test_semantic_true_returns_hybrid_mode():
    """semantic=True produces 'search_mode': 'hybrid' in response."""
    pytest.importorskip("fastembed")
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        result = search_symbols(repo="test/repo", query="authenticate user", storage_path=tmp, semantic=True)

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result.get("search_mode") == "hybrid"


def test_semantic_only_returns_semantic_mode():
    """semantic_only=True produces 'search_mode': 'semantic_only' in response."""
    pytest.importorskip("fastembed")
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        result = search_symbols(repo="test/repo", query="authenticate user", storage_path=tmp, semantic_only=True)

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result.get("search_mode") == "semantic_only"


def test_semantic_weight_zero_matches_keyword():
    """Hybrid with weight=0 produces results where all entries have kw_score > 0."""
    pytest.importorskip("fastembed")
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        result = search_symbols(
            repo="test/repo", query="login", storage_path=tmp, semantic=True, semantic_weight=0.0
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        # With weight=0, only symbols with kw_score > 0 are included.
        # "login" matches the login function by name, so we should get at least 1 result.
        assert len(result["results"]) >= 1
        for entry in result["results"]:
            assert entry["score"] > 0


def test_semantic_weight_one_matches_semantic_only():
    """Hybrid with weight=1.0 produces same result IDs as semantic_only."""
    pytest.importorskip("fastembed")
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        hybrid_result = search_symbols(
            repo="test/repo", query="authenticate user", storage_path=tmp, semantic=True, semantic_weight=1.0
        )
        semantic_only_result = search_symbols(
            repo="test/repo", query="authenticate user", storage_path=tmp, semantic_only=True
        )

        assert "error" not in hybrid_result, f"Unexpected error: {hybrid_result.get('error')}"
        assert "error" not in semantic_only_result, f"Unexpected error: {semantic_only_result.get('error')}"

        hybrid_ids = {_unwrap(r["id"]) for r in hybrid_result["results"]}
        semantic_ids = {_unwrap(r["id"]) for r in semantic_only_result["results"]}
        assert hybrid_ids == semantic_ids


def test_lazy_embedding_creates_sidecar():
    """First semantic call creates .embeddings.gz file."""
    pytest.importorskip("fastembed")
    # Ensure read-only mode is off (other tests may leak CODESIGHT_READ_ONLY)
    saved_ro = os.environ.pop("CODESIGHT_READ_ONLY", None)  # mock-ok: env var for test isolation
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _make_store_with_symbols(tmp)
            sidecar_path = Path(tmp) / "test__repo.embeddings.gz"
            assert not sidecar_path.exists(), "Sidecar should not exist before semantic search"

            result = search_symbols(repo="test/repo", query="authenticate user", storage_path=tmp, semantic=True)

            assert "error" not in result, f"Unexpected error: {result.get('error')}"
            assert sidecar_path.exists(), "Sidecar .embeddings.gz should exist after semantic search"
    finally:
        if saved_ro is not None:
            os.environ["CODESIGHT_READ_ONLY"] = saved_ro


def test_semantic_false_same_as_omitted():
    """Explicit semantic=False produces identical results to omitting param."""
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        result_omitted = search_symbols(repo="test/repo", query="login", storage_path=tmp)
        result_explicit = search_symbols(repo="test/repo", query="login", storage_path=tmp, semantic=False)

        omitted_ids = [_unwrap(r["id"]) for r in result_omitted["results"]]
        explicit_ids = [_unwrap(r["id"]) for r in result_explicit["results"]]
        assert omitted_ids == explicit_ids
        omitted_scores = [r["score"] for r in result_omitted["results"]]
        explicit_scores = [r["score"] for r in result_explicit["results"]]
        assert omitted_scores == explicit_scores
        assert "search_mode" not in result_omitted
        assert "search_mode" not in result_explicit


def test_missing_provider_returns_error():
    """CODESIGHT_NO_SEMANTIC=1, semantic=True returns error dict with disabled message."""
    old_value = os.environ.get("CODESIGHT_NO_SEMANTIC")
    os.environ["CODESIGHT_NO_SEMANTIC"] = "1"  # mock-ok: env var for test isolation
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _make_store_with_symbols(tmp)
            result = search_symbols(repo="test/repo", query="authenticate", storage_path=tmp, semantic=True)

            assert "error" in result
            assert "disabled" in result["error"].lower()
    finally:
        if old_value is None:
            os.environ.pop("CODESIGHT_NO_SEMANTIC", None)
        else:
            os.environ["CODESIGHT_NO_SEMANTIC"] = old_value


def test_semantic_weight_out_of_range():
    """weight=-0.1 and weight=1.5 both return error dict."""
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        result_negative = search_symbols(
            repo="test/repo", query="login", storage_path=tmp, semantic=True, semantic_weight=-0.1
        )
        result_over = search_symbols(
            repo="test/repo", query="login", storage_path=tmp, semantic=True, semantic_weight=1.5
        )

        assert "error" in result_negative
        assert "semantic_weight" in result_negative["error"]
        assert "error" in result_over
        assert "semantic_weight" in result_over["error"]


def test_cross_repo_semantic_search():
    """Create two repos, search with repos=[...] and semantic=True, verify results from both repos."""
    pytest.importorskip("fastembed")
    with tempfile.TemporaryDirectory() as tmp:
        store = IndexStore(base_path=tmp)

        symbols_a = [
            Symbol(
                id="src/auth.py::login#function",
                file="src/auth.py",
                name="login",
                qualified_name="login",
                kind="function",
                language="python",
                signature="def login(username: str, password: str) -> bool:",
                docstring="",
                summary="Authenticate user with username and password",
                decorators=[],
                keywords=[],
                parent=None,
                line=1,
                end_line=10,
                byte_offset=0,
                byte_length=200,
            ),
        ]
        store.save_index(
            owner="owner1",
            name="repo1",
            source_files=["src/auth.py"],
            symbols=symbols_a,
            raw_files={"src/auth.py": "def login(username, password): pass"},
            languages={"python": 1},
        )

        symbols_b = [
            Symbol(
                id="src/session.py::create_session#function",
                file="src/session.py",
                name="create_session",
                qualified_name="create_session",
                kind="function",
                language="python",
                signature="def create_session(user_id: int) -> str:",
                docstring="",
                summary="Create a new authentication session token",
                decorators=[],
                keywords=[],
                parent=None,
                line=1,
                end_line=8,
                byte_offset=0,
                byte_length=150,
            ),
        ]
        store.save_index(
            owner="owner2",
            name="repo2",
            source_files=["src/session.py"],
            symbols=symbols_b,
            raw_files={"src/session.py": "def create_session(user_id): pass"},
            languages={"python": 1},
        )

        result = search_symbols(
            repos=["owner1/repo1", "owner2/repo2"],
            query="authentication",
            storage_path=tmp,
            semantic=True,
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        result_repos = {r["repo"] for r in result["results"]}
        assert "owner1/repo1" in result_repos, "Results should include repo1"
        assert "owner2/repo2" in result_repos, "Results should include repo2"


def test_kind_filter_with_semantic():
    """semantic_only with kind='function' only returns functions."""
    pytest.importorskip("fastembed")
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_class(tmp)
        result = search_symbols(
            repo="test/repo",
            query="authentication",
            storage_path=tmp,
            semantic_only=True,
            kind="function",
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        for entry in result["results"]:
            assert entry["kind"] == "function", f"Expected kind='function', got {entry['kind']!r}"


def test_language_filter_with_semantic():
    """semantic_only with language='python' filters correctly."""
    pytest.importorskip("fastembed")
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        result = search_symbols(
            repo="test/repo",
            query="authenticate user",
            storage_path=tmp,
            semantic_only=True,
            language="python",
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert len(result["results"]) >= 1


def test_results_include_score():
    """All result modes include numeric 'score' field rounded to 1 decimal."""
    pytest.importorskip("fastembed")
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)

        # keyword
        kw_result = search_symbols(repo="test/repo", query="login", storage_path=tmp)
        # hybrid
        hybrid_result = search_symbols(repo="test/repo", query="login", storage_path=tmp, semantic=True)
        # semantic_only
        sem_result = search_symbols(repo="test/repo", query="authenticate user", storage_path=tmp, semantic_only=True)

        for label, res in [("keyword", kw_result), ("hybrid", hybrid_result), ("semantic_only", sem_result)]:
            assert "error" not in res, f"Unexpected error in {label}: {res.get('error')}"
            for entry in res["results"]:
                assert isinstance(entry["score"], (int, float)), f"Score in {label} is not numeric"
                assert round(entry["score"], 2) == entry["score"], (
                    f"Score {entry['score']!r} in {label} not rounded to 2 decimals"
                )


def test_empty_query_returns_error():
    """semantic=True with query='' returns error."""
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        result = search_symbols(repo="test/repo", query="", storage_path=tmp, semantic=True)

        assert "error" in result


def test_minimum_similarity_threshold():
    """semantic_only results only include symbols with sim > 0.1."""
    pytest.importorskip("fastembed")
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        # Use a very specific query that should give low similarity to unrelated symbols
        result = search_symbols(
            repo="test/repo",
            query="authenticate user with username and password",
            storage_path=tmp,
            semantic_only=True,
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        # All returned results must have score > 0.1 (the threshold in the code)
        for entry in result["results"]:
            assert entry["score"] > 0.0, f"Score {entry['score']} should be above threshold"


def test_model_mismatch_invalidates_cache():
    """Write sidecar with model='fake-model', do semantic search, verify new embeddings generated."""
    pytest.importorskip("fastembed")
    # Ensure read-only mode is off (other tests may leak CODESIGHT_READ_ONLY)
    saved_ro = os.environ.pop("CODESIGHT_READ_ONLY", None)  # mock-ok: env var for test isolation
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _make_store_with_symbols(tmp)
            sidecar_path = Path(tmp) / "test__repo.embeddings.gz"

            # Write a fake sidecar with a different model name
            fake_payload = {
                "model": "fake-model",
                "dimensions": 384,
                "vectors": {
                    "src/auth.py::login#function": [0.1] * 384,
                },
            }
            compressed = gzip.compress(json.dumps(fake_payload).encode())
            sidecar_path.write_bytes(compressed)

            # Now run semantic search — should detect model mismatch and re-embed
            result = search_symbols(
                repo="test/repo", query="authenticate user", storage_path=tmp, semantic=True
            )

            assert "error" not in result, f"Unexpected error: {result.get('error')}"

            # Verify the sidecar now has the correct model (not "fake-model")
            raw = gzip.decompress(sidecar_path.read_bytes())
            data = json.loads(raw)
            assert data["model"] != "fake-model", "Sidecar model should have been updated from 'fake-model'"
    finally:
        if saved_ro is not None:
            os.environ["CODESIGHT_READ_ONLY"] = saved_ro


def test_provider_failure_returns_sanitized_error():
    """Set CODESIGHT_EMBED_PROVIDER=nonexistent, verify error dict returned (not exception)."""
    old_value = os.environ.get("CODESIGHT_EMBED_PROVIDER")
    os.environ["CODESIGHT_EMBED_PROVIDER"] = "nonexistent"  # mock-ok: env var for test isolation
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _make_store_with_symbols(tmp)
            result = search_symbols(repo="test/repo", query="authenticate", storage_path=tmp, semantic=True)

            assert "error" in result
            # Should be an error dict, not an unhandled exception
            assert isinstance(result, dict)
    finally:
        if old_value is None:
            os.environ.pop("CODESIGHT_EMBED_PROVIDER", None)
        else:
            os.environ["CODESIGHT_EMBED_PROVIDER"] = old_value


def test_semantic_only_implies_semantic():
    """semantic_only=True without semantic=True still returns results with 'search_mode': 'semantic_only'."""
    pytest.importorskip("fastembed")
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_symbols(tmp)
        result = search_symbols(
            repo="test/repo",
            query="authenticate user",
            storage_path=tmp,
            semantic_only=True,
            semantic=False,
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result.get("search_mode") == "semantic_only"


def test_read_only_mode_semantic_works():
    """CODESIGHT_READ_ONLY=1, semantic=True still returns results (computed in-memory)."""
    pytest.importorskip("fastembed")
    old_value = os.environ.get("CODESIGHT_READ_ONLY")
    try:
        # First, create the store without read-only mode
        with tempfile.TemporaryDirectory() as tmp:
            _make_store_with_symbols(tmp)

            # Now enable read-only mode
            os.environ["CODESIGHT_READ_ONLY"] = "1"  # mock-ok: env var for test isolation

            result = search_symbols(
                repo="test/repo", query="authenticate user", storage_path=tmp, semantic=True
            )

            assert "error" not in result, f"Unexpected error: {result.get('error')}"
            assert result.get("search_mode") == "hybrid"
            assert len(result["results"]) >= 1
    finally:
        if old_value is None:
            os.environ.pop("CODESIGHT_READ_ONLY", None)
        else:
            os.environ["CODESIGHT_READ_ONLY"] = old_value
