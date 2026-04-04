"""Tests for EmbeddingStore — save/load, concurrency, validation, read-only."""

from __future__ import annotations

import gzip
import json
import os
import threading
from pathlib import Path

import pytest

from codesight_mcp.embeddings.store import EmbeddingStore


@pytest.fixture(autouse=True)
def _clean_read_only_env():
    """Ensure CODESIGHT_READ_ONLY is not set — other tests (CLI dispatch) may leak it."""
    # mock-ok: env var cleanup for test isolation, no real service to substitute
    old = os.environ.pop("CODESIGHT_READ_ONLY", None)
    yield
    if old is not None:
        os.environ["CODESIGHT_READ_ONLY"] = old
    else:
        os.environ.pop("CODESIGHT_READ_ONLY", None)


def _make_store(tmp_path: Path, owner: str = "test-owner", name: str = "test-repo") -> EmbeddingStore:
    return EmbeddingStore(owner, name, storage_path=str(tmp_path))


# ------------------------------------------------------------------
# Basic operations
# ------------------------------------------------------------------


class TestBasicOperations:
    def test_set_and_get(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        vec = [1.0, 2.0, 3.0]
        store.set("sym-a", vec)
        assert store.get("sym-a") == vec

    def test_get_empty_store_returns_none(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        assert store.get("nonexistent") is None

    def test_file_does_not_exist_initializes_empty(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.load()
        assert store.get("anything") is None

    def test_missing_returns_correct_ids(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.set("a", [1.0])
        store.set("b", [2.0])
        result = store.missing(["a", "b", "c", "d"])
        assert result == ["c", "d"]

    def test_invalidate_removes_vectors(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.set("x", [1.0, 2.0])
        assert store.get("x") is not None
        store.invalidate(["x"])
        assert store.get("x") is None


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------


class TestPersistence:
    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.model = "text-embedding-3-small"
        store.dimensions = 3
        store.set("sym-1", [0.1, 0.2, 0.3])
        store.set("sym-2", [0.4, 0.5, 0.6])
        store.save()

        store2 = _make_store(tmp_path)
        store2.load()
        assert store2.get("sym-1") == [0.1, 0.2, 0.3]
        assert store2.get("sym-2") == [0.4, 0.5, 0.6]

    def test_model_dimensions_preserved(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.model = "nomic-embed-text"
        store.dimensions = 768
        store.set("s1", [float(i) for i in range(768)])
        store.save()

        store2 = _make_store(tmp_path)
        store2.load()
        assert store2.model == "nomic-embed-text"
        assert store2.dimensions == 768

    def test_gzip_format(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.model = "m"
        store.dimensions = 2
        store.set("a", [1.0, 2.0])
        store.save()

        sidecar = tmp_path / "test-owner__test-repo.embeddings.gz"
        raw = sidecar.read_bytes()
        # Gzip magic bytes
        assert raw[:2] == b"\x1f\x8b"
        # Verify roundtrip through gzip
        payload = json.loads(gzip.decompress(raw))
        assert payload["vectors"]["a"] == [1.0, 2.0]

    def test_no_tmp_files_after_save(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.model = "m"
        store.dimensions = 1
        store.set("x", [1.0])
        store.save()

        tmp_files = list(tmp_path.glob("*.tmp.*"))
        assert tmp_files == []


# ------------------------------------------------------------------
# Schema validation
# ------------------------------------------------------------------


class TestSchemaValidation:
    def test_corrupted_gzip(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "test-owner__test-repo.embeddings.gz"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_bytes(b"this is not gzip at all")

        store = _make_store(tmp_path)
        store.load()
        assert store.get("anything") is None

    def test_malformed_json(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "test-owner__test-repo.embeddings.gz"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_bytes(gzip.compress(b"not valid json {{{"))

        store = _make_store(tmp_path)
        store.load()
        assert store.get("anything") is None

    def test_wrong_dimensions_rejected(self, tmp_path: Path) -> None:
        payload = {
            "model": "m",
            "dimensions": 3,
            "vectors": {
                "good": [1.0, 2.0, 3.0],
                "bad": [1.0, 2.0],  # only 2 dims
            },
        }
        sidecar = tmp_path / "test-owner__test-repo.embeddings.gz"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_bytes(gzip.compress(json.dumps(payload).encode()))

        store = _make_store(tmp_path)
        store.load()
        assert store.get("good") == [1.0, 2.0, 3.0]
        assert store.get("bad") is None

    def test_nan_inf_rejected(self, tmp_path: Path) -> None:
        payload = {
            "model": "m",
            "dimensions": 2,
            "vectors": {
                "has-nan": [1.0, float("nan")],
                "has-inf": [float("inf"), 2.0],
                "ok": [1.0, 2.0],
            },
        }
        # json.dumps doesn't handle nan/inf natively — write raw
        raw = json.dumps(payload, allow_nan=True).encode()
        sidecar = tmp_path / "test-owner__test-repo.embeddings.gz"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_bytes(gzip.compress(raw))

        store = _make_store(tmp_path)
        store.load()
        assert store.get("has-nan") is None
        assert store.get("has-inf") is None
        assert store.get("ok") == [1.0, 2.0]

    def test_non_dict_top_level(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "test-owner__test-repo.embeddings.gz"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_bytes(gzip.compress(json.dumps([1, 2, 3]).encode()))

        store = _make_store(tmp_path)
        store.load()
        assert store.get("anything") is None


# ------------------------------------------------------------------
# Read-only mode
# ------------------------------------------------------------------


class TestReadOnly:
    def test_read_only_save_is_noop(self, tmp_path: Path) -> None:
        old_val = os.environ.get("CODESIGHT_READ_ONLY")
        os.environ["CODESIGHT_READ_ONLY"] = "1"  # mock-ok: env var for read-only mode, no real service to substitute
        try:
            store = _make_store(tmp_path)
            store.model = "m"
            store.dimensions = 1
            store.set("x", [1.0])
            store.save()

            sidecar = tmp_path / "test-owner__test-repo.embeddings.gz"
            assert not sidecar.exists()
        finally:
            if old_val is None:
                os.environ.pop("CODESIGHT_READ_ONLY", None)
            else:
                os.environ["CODESIGHT_READ_ONLY"] = old_val

    def test_read_only_in_memory_still_works(self, tmp_path: Path) -> None:
        old_val = os.environ.get("CODESIGHT_READ_ONLY")
        os.environ["CODESIGHT_READ_ONLY"] = "1"  # mock-ok: env var for read-only mode, no real service to substitute
        try:
            store = _make_store(tmp_path)
            store.set("x", [1.0])
            assert store.get("x") == [1.0]
        finally:
            if old_val is None:
                os.environ.pop("CODESIGHT_READ_ONLY", None)
            else:
                os.environ["CODESIGHT_READ_ONLY"] = old_val


# ------------------------------------------------------------------
# Concurrency
# ------------------------------------------------------------------


class TestConcurrency:
    def test_concurrent_save_merge(self, tmp_path: Path) -> None:
        """Two threads set different symbols and save — both must appear."""
        base = _make_store(tmp_path)
        base.model = "m"
        base.dimensions = 2
        base.save()

        errors: list[Exception] = []
        barrier = threading.Barrier(2)

        def writer(sym_id: str, vec: list[float]) -> None:
            try:
                s = _make_store(tmp_path)
                s.model = "m"
                s.dimensions = 2
                s.set(sym_id, vec)
                barrier.wait(timeout=5)
                s.save()
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=writer, args=("X", [1.0, 2.0]))
        t2 = threading.Thread(target=writer, args=("Y", [3.0, 4.0]))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"

        final = _make_store(tmp_path)
        final.load()
        assert final.get("X") == [1.0, 2.0]
        assert final.get("Y") == [3.0, 4.0]

    def test_concurrent_invalidation(self, tmp_path: Path) -> None:
        """Thread A invalidates X, thread B adds Y — final has Y but not X.

        The invalidator saves last to guarantee its tombstone wins over
        the adder's reload-merge (which would otherwise resurrect X).
        """
        pre = _make_store(tmp_path)
        pre.model = "m"
        pre.dimensions = 2
        pre.set("X", [1.0, 2.0])
        pre.save()

        errors: list[Exception] = []
        # First barrier: both threads prepare before saving
        prep_barrier = threading.Barrier(2)
        # Second barrier: adder signals it saved; invalidator waits then saves
        adder_done = threading.Event()

        def invalidator() -> None:
            try:
                s = _make_store(tmp_path)
                s.invalidate(["X"])
                prep_barrier.wait(timeout=5)
                adder_done.wait(timeout=5)
                s.save()
            except Exception as exc:
                errors.append(exc)

        def adder() -> None:
            try:
                s = _make_store(tmp_path)
                s.model = "m"
                s.dimensions = 2
                s.set("Y", [3.0, 4.0])
                prep_barrier.wait(timeout=5)
                s.save()
                adder_done.set()
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=invalidator)
        t2 = threading.Thread(target=adder)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"

        final = _make_store(tmp_path)
        final.load()
        assert final.get("X") is None
        assert final.get("Y") == [3.0, 4.0]


# ------------------------------------------------------------------
# Tombstone semantics
# ------------------------------------------------------------------


class TestTombstones:
    def test_set_clears_tombstone(self, tmp_path: Path) -> None:
        """invalidate(X) then set(X) → X present in final save."""
        store = _make_store(tmp_path)
        store.model = "m"
        store.dimensions = 2
        store.set("X", [1.0, 2.0])
        store.invalidate(["X"])
        assert store.get("X") is None

        store.set("X", [9.0, 8.0])
        store.save()

        final = _make_store(tmp_path)
        final.load()
        assert final.get("X") == [9.0, 8.0]
