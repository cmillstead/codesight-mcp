"""Tests for storage identifier hardening."""

import json
import tempfile

import pytest

from ironmunch.storage.index_store import IndexStore
from ironmunch.core.validation import ValidationError


class TestIdentifierSanitization:
    def test_normal_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = IndexStore(tmp)
            path = store._index_path("owner", "repo")
            assert "owner-repo.json" in str(path)

    def test_traversal_in_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = IndexStore(tmp)
            with pytest.raises(ValidationError):
                store._index_path("..", "repo")

    def test_slash_in_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = IndexStore(tmp)
            with pytest.raises(ValidationError):
                store._index_path("owner", "repo/../../etc")

    def test_null_byte_in_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = IndexStore(tmp)
            with pytest.raises(ValidationError):
                store._index_path("owner\x00evil", "repo")

    def test_content_dir_same_sanitization(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = IndexStore(tmp)
            with pytest.raises(ValidationError):
                store._content_dir("../escape", "repo")


class TestIndexSizeValidation:
    def test_oversized_index_rejected(self):
        """Index files exceeding MAX_INDEX_SIZE are rejected on load."""
        with tempfile.TemporaryDirectory() as tmp:
            store = IndexStore(tmp)

            # Save a valid index first
            store.save_index(
                owner="test",
                name="repo",
                source_files=["main.py"],
                symbols=[],
                raw_files={"main.py": ""},
                languages={"python": 1},
            )

            # Bloat the index file beyond the limit
            index_path = store._index_path("test", "repo")
            with open(index_path, "r") as f:
                data = json.load(f)

            # Pad with junk to exceed 50 MB
            from ironmunch.core.limits import MAX_INDEX_SIZE
            data["_pad"] = "x" * (MAX_INDEX_SIZE + 1)
            with open(index_path, "w") as f:
                json.dump(data, f)

            with pytest.raises(ValueError, match="exceeds maximum size"):
                store.load_index("test", "repo")

    def test_normal_size_index_loads(self):
        """Index files within the size limit load normally."""
        with tempfile.TemporaryDirectory() as tmp:
            store = IndexStore(tmp)

            store.save_index(
                owner="test",
                name="repo",
                source_files=["main.py"],
                symbols=[],
                raw_files={"main.py": ""},
                languages={"python": 1},
            )

            loaded = store.load_index("test", "repo")
            assert loaded is not None
            assert loaded.repo == "test/repo"
