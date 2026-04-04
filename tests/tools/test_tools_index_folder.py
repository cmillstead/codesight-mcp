"""Functional tests for the index_folder tool (TEST-MED-4)."""

import pytest

from codesight_mcp.storage.index_store import IndexStore
from codesight_mcp.tools.index_folder import index_folder


def test_no_source_files_returns_no_symbols(tmp_path):
    """A folder with no parseable source files returns an error (no symbols found)."""
    # tmp_path is an allowed root containing only non-parseable content
    result = index_folder(
        path=str(tmp_path),
        use_ai_summaries=False,
        storage_path=str(tmp_path / "_storage"),
        allowed_roots=[str(tmp_path)],
    )

    # The function reports an error when no files are found — success is False
    assert result.get("success") is False
    assert "error" in result


def test_valid_folder_with_python_file(tmp_path):
    """Indexing a folder with one Python file returns success=True with symbols."""
    py_file = tmp_path / "sample.py"
    py_file.write_text(
        "def hello():\n    \"\"\"Say hello.\"\"\"\n    return 'hello'\n"
    )

    result = index_folder(
        path=str(tmp_path),
        use_ai_summaries=False,
        storage_path=str(tmp_path / "_storage"),
        allowed_roots=[str(tmp_path)],
    )

    assert result.get("success") is True, f"Expected success, got: {result}"
    assert result.get("symbol_count", 0) > 0
    assert result.get("file_count", 0) > 0


def test_non_parseable_file_type_still_succeeds_if_py_present(tmp_path):
    """A folder with a non-parseable file type alongside a .py file still succeeds."""
    # Write a parseable Python file
    py_file = tmp_path / "main.py"
    py_file.write_text(
        "def compute(x):\n    \"\"\"Compute something.\"\"\"\n    return x * 2\n"
    )
    # Write a non-parseable file (e.g., .txt)
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("This is just a text file, not parseable code.\n")

    result = index_folder(
        path=str(tmp_path),
        use_ai_summaries=False,
        storage_path=str(tmp_path / "_storage"),
        allowed_roots=[str(tmp_path)],
    )

    # Should succeed despite having a non-parseable file
    assert result.get("success") is True, f"Expected success, got: {result}"
    # No hard error — just succeeds (warnings may or may not be present)
    assert "error" not in result


def _py_file_content():
    return "def hello():\n    \"\"\"Say hello.\"\"\"\n    return 'hello'\n"


class TestStorageKeyCollision:
    """ADV-HIGH-2: Two directories with the same basename must get distinct storage keys."""

    def test_same_basename_different_paths_get_different_keys(self, tmp_path):
        """Two directories named 'myapp' at different paths produce different repo keys."""
        storage = tmp_path / "_storage"

        dir_a = tmp_path / "projects" / "myapp"
        dir_a.mkdir(parents=True)
        (dir_a / "main.py").write_text(_py_file_content())

        dir_b = tmp_path / "sandbox" / "myapp"
        dir_b.mkdir(parents=True)
        (dir_b / "main.py").write_text(_py_file_content())

        result_a = index_folder(
            path=str(dir_a),
            use_ai_summaries=False,
            storage_path=str(storage),
            allowed_roots=[str(tmp_path)],
        )
        result_b = index_folder(
            path=str(dir_b),
            use_ai_summaries=False,
            storage_path=str(storage),
            allowed_roots=[str(tmp_path)],
        )

        assert result_a.get("success") is True, f"dir_a indexing failed: {result_a}"
        assert result_b.get("success") is True, f"dir_b indexing failed: {result_b}"
        # The repo keys must differ even though both basenames are "myapp"
        assert result_a["repo"] != result_b["repo"], (
            f"Expected distinct repo keys, both got: {result_a['repo']!r}"
        )

    def test_second_index_does_not_overwrite_first(self, tmp_path):
        """Indexing a second 'myapp' directory must not clobber the first index."""
        storage = tmp_path / "_storage"

        dir_a = tmp_path / "projects" / "myapp"
        dir_a.mkdir(parents=True)
        (dir_a / "alpha.py").write_text("def alpha():\n    return 'a'\n")

        dir_b = tmp_path / "sandbox" / "myapp"
        dir_b.mkdir(parents=True)
        (dir_b / "beta.py").write_text("def beta():\n    return 'b'\n")

        result_a = index_folder(
            path=str(dir_a),
            use_ai_summaries=False,
            storage_path=str(storage),
            allowed_roots=[str(tmp_path)],
        )
        result_b = index_folder(
            path=str(dir_b),
            use_ai_summaries=False,
            storage_path=str(storage),
            allowed_roots=[str(tmp_path)],
        )

        assert result_a.get("success") is True
        assert result_b.get("success") is True

        # Extract owner/name from each repo key and load independently
        store = IndexStore(base_path=str(storage))
        owner_a, name_a = result_a["repo"].split("/", 1)
        owner_b, name_b = result_b["repo"].split("/", 1)

        idx_a = store.load_index(owner_a, name_a)
        idx_b = store.load_index(owner_b, name_b)

        assert idx_a is not None, "First index was clobbered"
        assert idx_b is not None, "Second index not found"

        files_a = set(idx_a.source_files)
        files_b = set(idx_b.source_files)
        assert "alpha.py" in files_a, f"alpha.py missing from first index: {files_a}"
        assert "beta.py" in files_b, f"beta.py missing from second index: {files_b}"

    def test_list_repos_shows_both_as_distinct(self, tmp_path):
        """list_repos must return two distinct entries after indexing two same-basename dirs."""
        storage = tmp_path / "_storage"

        dir_a = tmp_path / "root1" / "myapp"
        dir_a.mkdir(parents=True)
        (dir_a / "mod.py").write_text("def mod_a():\n    pass\n")

        dir_b = tmp_path / "root2" / "myapp"
        dir_b.mkdir(parents=True)
        (dir_b / "mod.py").write_text("def mod_b():\n    pass\n")

        result_a = index_folder(
            path=str(dir_a),
            use_ai_summaries=False,
            storage_path=str(storage),
            allowed_roots=[str(tmp_path)],
        )
        result_b = index_folder(
            path=str(dir_b),
            use_ai_summaries=False,
            storage_path=str(storage),
            allowed_roots=[str(tmp_path)],
        )

        assert result_a.get("success") is True
        assert result_b.get("success") is True

        store = IndexStore(base_path=str(storage))
        repos = store.list_repos()
        repo_keys = {r["repo"] for r in repos}

        assert result_a["repo"] in repo_keys, f"{result_a['repo']!r} not in {repo_keys}"
        assert result_b["repo"] in repo_keys, f"{result_b['repo']!r} not in {repo_keys}"
        assert result_a["repo"] != result_b["repo"], "Repo keys must be distinct"


class TestEmbeddingInvalidation:
    """Embedding sidecar invalidation during incremental and full reindexing."""

    @pytest.fixture(autouse=True)
    def _clean_read_only_env(self):
        """Ensure CODESIGHT_READ_ONLY is not set — CLI dispatch tests may leak it."""
        import os
        old = os.environ.pop("CODESIGHT_READ_ONLY", None)  # mock-ok: env var cleanup for test isolation
        yield
        if old is not None:
            os.environ["CODESIGHT_READ_ONLY"] = old
        else:
            os.environ.pop("CODESIGHT_READ_ONLY", None)

    @staticmethod
    def _init_git_repo(folder):
        """Initialize a git repo and commit all files in *folder*."""
        import subprocess

        subprocess.run(["git", "init"], cwd=str(folder), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(folder), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(folder), capture_output=True, check=True)
        subprocess.run(["git", "add", "."], cwd=str(folder), capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(folder), capture_output=True, check=True)

    @staticmethod
    def _commit_all(folder, msg="update"):
        import subprocess

        subprocess.run(["git", "add", "."], cwd=str(folder), capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=str(folder), capture_output=True, check=True)

    @staticmethod
    def _populate_embeddings(owner, name, storage_path, symbol_ids):
        """Create an EmbeddingStore sidecar with fake vectors for *symbol_ids*."""
        from codesight_mcp.embeddings.store import EmbeddingStore

        embed_store = EmbeddingStore(owner, name, storage_path)
        embed_store.model = "test-model"
        embed_store.dimensions = 3
        for sid in symbol_ids:
            embed_store.set(sid, [1.0, 2.0, 3.0])
        embed_store.save()

    @staticmethod
    def _load_embedding_ids(owner, name, storage_path):
        """Load the EmbeddingStore and return the set of stored symbol IDs."""
        from codesight_mcp.embeddings.store import EmbeddingStore

        embed_store = EmbeddingStore(owner, name, storage_path)
        embed_store.load()
        return set(embed_store._vectors.keys())

    def test_incremental_reindex_invalidates_changed_file_embeddings(self, tmp_path):
        """Modifying a file during incremental reindex invalidates its symbol embeddings."""
        src_dir = tmp_path / "project"
        src_dir.mkdir()
        storage = str(tmp_path / "_storage")

        (src_dir / "file_a.py").write_text("def sym_a():\n    return 1\n")
        (src_dir / "file_b.py").write_text("def sym_b():\n    return 2\n")
        self._init_git_repo(src_dir)

        # First index
        result1 = index_folder(
            path=str(src_dir), use_ai_summaries=False,
            storage_path=storage, allowed_roots=[str(tmp_path)],
        )
        assert result1.get("success") is True

        # Extract owner/name and load symbols to get IDs
        owner, name = result1["repo"].split("/", 1)
        store = IndexStore(base_path=storage)
        idx = store.load_index(owner, name)
        assert idx is not None

        sym_ids_by_file = {}
        for sym in idx.symbols:
            f = sym.get("file", "")
            sym_ids_by_file.setdefault(f, []).append(sym["id"])

        all_ids = [sym["id"] for sym in idx.symbols]
        self._populate_embeddings(owner, name, storage, all_ids)

        # Modify file_a.py and commit
        (src_dir / "file_a.py").write_text("def sym_a():\n    return 999\n")
        self._commit_all(src_dir, "modify file_a")

        # Incremental reindex
        result2 = index_folder(
            path=str(src_dir), use_ai_summaries=False,
            storage_path=storage, allowed_roots=[str(tmp_path)],
        )
        assert result2.get("success") is True
        assert result2.get("incremental") is True

        # Verify: file_a's old embeddings gone, file_b's remain
        remaining = self._load_embedding_ids(owner, name, storage)
        for sid in sym_ids_by_file.get("file_a.py", []):
            assert sid not in remaining, f"Stale embedding {sid} from file_a.py should be invalidated"
        for sid in sym_ids_by_file.get("file_b.py", []):
            assert sid in remaining, f"Embedding {sid} from file_b.py should still exist"

    def test_incremental_reindex_invalidates_deleted_file_embeddings(self, tmp_path):
        """Deleting a file during incremental reindex invalidates its symbol embeddings."""
        src_dir = tmp_path / "project"
        src_dir.mkdir()
        storage = str(tmp_path / "_storage")

        (src_dir / "file_a.py").write_text("def sym_a():\n    return 1\n")
        (src_dir / "file_b.py").write_text("def sym_b():\n    return 2\n")
        self._init_git_repo(src_dir)

        # First index
        result1 = index_folder(
            path=str(src_dir), use_ai_summaries=False,
            storage_path=storage, allowed_roots=[str(tmp_path)],
        )
        assert result1.get("success") is True

        owner, name = result1["repo"].split("/", 1)
        store = IndexStore(base_path=storage)
        idx = store.load_index(owner, name)
        assert idx is not None

        sym_ids_by_file = {}
        for sym in idx.symbols:
            f = sym.get("file", "")
            sym_ids_by_file.setdefault(f, []).append(sym["id"])

        all_ids = [sym["id"] for sym in idx.symbols]
        self._populate_embeddings(owner, name, storage, all_ids)

        # Delete file_a.py and commit
        (src_dir / "file_a.py").unlink()
        self._commit_all(src_dir, "delete file_a")

        # Incremental reindex
        result2 = index_folder(
            path=str(src_dir), use_ai_summaries=False,
            storage_path=storage, allowed_roots=[str(tmp_path)],
        )
        assert result2.get("success") is True
        assert result2.get("incremental") is True

        # Verify: file_a's embeddings gone, file_b's remain
        remaining = self._load_embedding_ids(owner, name, storage)
        for sid in sym_ids_by_file.get("file_a.py", []):
            assert sid not in remaining, f"Stale embedding {sid} from deleted file_a.py should be invalidated"
        for sid in sym_ids_by_file.get("file_b.py", []):
            assert sid in remaining, f"Embedding {sid} from file_b.py should still exist"

    def test_full_reindex_invalidates_changed_embeddings(self, tmp_path):
        """A full reindex invalidates changed/removed symbols but preserves unchanged ones."""
        src_dir = tmp_path / "project"
        src_dir.mkdir()
        storage = str(tmp_path / "_storage")

        (src_dir / "file_a.py").write_text("def sym_a():\n    return 1\n")
        (src_dir / "file_b.py").write_text("def sym_b():\n    return 2\n")

        # First index (no git — forces full reindex path)
        result1 = index_folder(
            path=str(src_dir), use_ai_summaries=False,
            storage_path=storage, allowed_roots=[str(tmp_path)],
        )
        assert result1.get("success") is True

        owner, name = result1["repo"].split("/", 1)
        store = IndexStore(base_path=storage)
        idx = store.load_index(owner, name)
        assert idx is not None

        # Separate symbol IDs by file
        ids_a = [s["id"] for s in idx.symbols if s.get("file", "").endswith("file_a.py")]
        ids_b = [s["id"] for s in idx.symbols if s.get("file", "").endswith("file_b.py")]
        all_ids = ids_a + ids_b
        assert len(ids_a) > 0
        assert len(ids_b) > 0
        self._populate_embeddings(owner, name, storage, all_ids)

        # Verify embeddings exist before reindex
        before = self._load_embedding_ids(owner, name, storage)
        assert len(before) == len(all_ids)

        # Change file_a (different signature), leave file_b unchanged
        (src_dir / "file_a.py").write_text("def sym_a(x):\n    return x + 1\n")

        # Full reindex (still no git — goes through finalize_index)
        result2 = index_folder(
            path=str(src_dir), use_ai_summaries=False,
            storage_path=storage, allowed_roots=[str(tmp_path)],
        )
        assert result2.get("success") is True
        assert "incremental" not in result2  # full reindex, not incremental

        # Verify: file_a's embeddings invalidated (signature changed), file_b's preserved
        remaining = self._load_embedding_ids(owner, name, storage)
        for sid in ids_a:
            assert sid not in remaining, f"Embedding {sid} from changed file_a.py should be invalidated"
        for sid in ids_b:
            assert sid in remaining, f"Embedding {sid} from unchanged file_b.py should survive"
