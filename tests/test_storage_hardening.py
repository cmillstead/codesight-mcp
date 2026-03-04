"""Tests for storage identifier hardening."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from ironmunch.storage.index_store import IndexStore
from ironmunch.core.validation import ValidationError


class TestIdentifierSanitization:
    def test_normal_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = IndexStore(tmp)
            path = store._index_path("owner", "repo")
            assert "owner__repo.json" in str(path)

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


class TestIncrementalSaveDeletedFilesTraversal:
    """SEC-HIGH-1: Verify traversal in deleted_files is blocked."""

    def test_traversal_in_deleted_files_blocked(self):
        """Deleted files with traversal paths must not delete outside content dir."""
        with tempfile.TemporaryDirectory() as tmp:
            store = IndexStore(tmp)

            # Create an initial index
            store.save_index(
                owner="test", name="repo",
                source_files=["main.py"],
                symbols=[], raw_files={"main.py": "print('hello')"},
                languages={"python": 1},
            )

            # Place a target file at the traversal destination
            target = Path(tmp) / "victim.txt"
            target.write_text("precious data")

            # Attempt incremental save with traversal in deleted_files
            store.incremental_save(
                owner="test", name="repo",
                changed_files=[], new_files=[],
                deleted_files=["../../victim.txt", "../victim.txt"],
                new_symbols=[], raw_files={},
                languages={"python": 1},
            )

            # Target file must survive
            assert target.exists(), "Traversal in deleted_files escaped content dir"
            assert target.read_text() == "precious data"

    def test_legitimate_deleted_files_still_work(self):
        """Normal file deletion in incremental save still works."""
        with tempfile.TemporaryDirectory() as tmp:
            store = IndexStore(tmp)

            store.save_index(
                owner="test", name="repo",
                source_files=["old.py"],
                symbols=[], raw_files={"old.py": "# old"},
                languages={"python": 1},
            )

            content_dir = store._content_dir("test", "repo")
            old_file = content_dir / "old.py"
            assert old_file.exists()

            store.incremental_save(
                owner="test", name="repo",
                changed_files=[], new_files=[],
                deleted_files=["old.py"],
                new_symbols=[], raw_files={},
                languages={"python": 1},
            )

            assert not old_file.exists(), "Legitimate deleted file should be removed"


class TestBasePathPermissions:
    """SEC-LOW-4: IndexStore base_path must be created with 0o700 permissions."""

    def test_base_path_mode_is_0o700(self):
        """base_path must have mode 0o700 after IndexStore construction."""
        with tempfile.TemporaryDirectory() as storage_tmp:
            base = Path(storage_tmp) / "idx"
            store = IndexStore(base_path=str(base))
            mode = os.stat(str(base)).st_mode & 0o777
            assert mode == 0o700, (
                f"base_path mode should be 0o700, got 0o{mode:o}"
            )


class TestLoadIndexNoFollow:
    """SEC-LOW-2: load_index must reject symlinks (O_NOFOLLOW)."""

    def test_symlink_index_returns_none(self):
        """load_index must return None when the index file is a symlink."""
        with tempfile.TemporaryDirectory() as storage_tmp:
            with tempfile.TemporaryDirectory() as other_tmp:
                store = IndexStore(base_path=storage_tmp)

                # Create a real index file first
                store.save_index(
                    owner="test", name="repo",
                    source_files=["main.py"],
                    symbols=[], raw_files={"main.py": "x = 1"},
                    languages={"python": 1},
                )

                # Locate the real index file and replace it with a symlink
                index_file = Path(storage_tmp) / "test__repo.json"
                assert index_file.exists()
                decoy = Path(other_tmp) / "decoy.txt"
                decoy.write_text("not a valid index")
                index_file.unlink()
                index_file.symlink_to(decoy)

                # load_index must return None rather than reading the symlink target
                result = store.load_index("test", "repo")
                assert result is None, (
                    "load_index must return None for a symlink index file"
                )
