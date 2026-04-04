"""Persistent vector storage for symbol embeddings.

Stores embedding vectors as a gzip-compressed JSON sidecar file alongside
the main code index.  Supports concurrent writers via file locking with
a reload-merge-tombstone pattern that prevents stale data resurrection.
"""

from __future__ import annotations

import gzip
import json
import logging
import math
import os
import threading
from pathlib import Path
from typing import Any

from codesight_mcp.core.locking import exclusive_file_lock
from codesight_mcp.security import sanitize_repo_identifier

logger = logging.getLogger(__name__)

_MAX_DECOMPRESSED_SIZE = 100 * 1024 * 1024  # 100 MB


class EmbeddingStore:
    """Persistent store for symbol embedding vectors.

    Vectors are kept in-memory after lazy load and flushed to a gzip-JSON
    sidecar file on ``save()``.  Concurrent writers are coordinated via
    an exclusive file lock with reload-merge-tombstone semantics so that
    no writer silently overwrites another's changes.
    """

    def __init__(
        self,
        owner: str,
        name: str,
        storage_path: str | None = None,
    ) -> None:
        owner = sanitize_repo_identifier(owner)
        name = sanitize_repo_identifier(name)

        base_path = Path(storage_path) if storage_path else Path.home() / ".code-index"
        slug = f"{owner}__{name}"
        self._path = base_path / f"{slug}.embeddings.gz"
        self._lock_path = base_path / f"{slug}.embeddings.lock"

        self._vectors: dict[str, list[float]] = {}
        self._invalidated: set[str] = set()
        self._loaded = False
        self._model: str = ""
        self._dimensions: int = 0
        self._read_only: bool = os.environ.get("CODESIGHT_READ_ONLY", "").lower() in (
            "1",
            "true",
            "yes",
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @dimensions.setter
    def dimensions(self, value: int) -> None:
        self._dimensions = value

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the sidecar file into memory.

        If the file does not exist the store initialises empty.  Corrupted
        or schema-invalid files are logged and silently replaced with an
        empty store so callers never crash.
        """
        self._loaded = True

        if not self._path.exists():
            return

        try:
            raw = self._decompress_limited(self._path)
        except (OSError, gzip.BadGzipFile, EOFError, ValueError) as exc:
            logger.warning("Corrupt gzip sidecar %s: %s — starting empty", self._path, exc)
            return

        try:
            data: Any = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Malformed JSON in %s: %s — starting empty", self._path, exc)
            return

        self._apply_payload(data)

    def save(self) -> None:
        """Persist in-memory vectors to disk with concurrent-writer safety.

        In read-only mode this is a no-op.  Otherwise the method acquires
        an exclusive file lock, reloads the on-disk state, merges the
        in-memory delta on top, applies tombstones, and atomically writes
        the result.
        """
        if self._read_only:
            logger.debug("Read-only mode — skipping save for %s", self._path)
            return

        with exclusive_file_lock(self._lock_path):
            disk_vectors: dict[str, list[float]] = {}
            disk_model = self._model
            disk_dimensions = self._dimensions

            if self._path.exists():
                try:
                    raw = self._decompress_limited(self._path)
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        disk_model = data.get("model", disk_model)
                        disk_dimensions = data.get("dimensions", disk_dimensions)
                        vecs = data.get("vectors", {})
                        if isinstance(vecs, dict):
                            disk_vectors = vecs
                except (OSError, gzip.BadGzipFile, EOFError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
                    logger.warning("Could not reload sidecar %s during save — using in-memory state", self._path)

            # Merge: disk first, then overlay in-memory (in-memory wins)
            merged = {**disk_vectors, **self._vectors}

            # Apply tombstones
            for sym_id in self._invalidated:
                merged.pop(sym_id, None)

            payload = {
                "model": self._model or disk_model,
                "dimensions": self._dimensions or disk_dimensions,
                "vectors": merged,
            }
            compressed = gzip.compress(json.dumps(payload).encode())
            self._atomic_write_bytes(self._path, compressed)

            # Successful write — clear tombstones and sync in-memory state
            self._invalidated.clear()
            self._vectors = merged

    def get(self, symbol_id: str) -> list[float] | None:
        """Return the cached vector for *symbol_id*, or ``None``."""
        self._ensure_loaded()
        return self._vectors.get(symbol_id)

    def set(self, symbol_id: str, vector: list[float]) -> None:
        """Store *vector* for *symbol_id*, clearing any pending tombstone."""
        self._ensure_loaded()
        self._vectors[symbol_id] = vector
        self._invalidated.discard(symbol_id)

    def missing(self, symbol_ids: list[str]) -> list[str]:
        """Return the subset of *symbol_ids* that have no cached vector."""
        self._ensure_loaded()
        return [sid for sid in symbol_ids if sid not in self._vectors]

    def invalidate(self, symbol_ids: list[str]) -> None:
        """Remove *symbol_ids* from the cache and mark them as tombstones."""
        self._ensure_loaded()
        for sid in symbol_ids:
            self._vectors.pop(sid, None)
            self._invalidated.add(sid)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _apply_payload(self, data: Any) -> None:
        """Validate and apply a parsed JSON payload to in-memory state."""
        if not isinstance(data, dict):
            logger.warning("Top-level JSON is not a dict in %s — starting empty", self._path)
            return

        required_keys = {"model", "dimensions", "vectors"}
        if not required_keys.issubset(data):
            logger.warning("Missing required keys in %s — starting empty", self._path)
            return

        if not isinstance(data["vectors"], dict):
            logger.warning("'vectors' is not a dict in %s — starting empty", self._path)
            return

        dimensions: int = data["dimensions"]
        self._model = data["model"]
        self._dimensions = dimensions

        for sym_id, vec in data["vectors"].items():
            if not isinstance(sym_id, str):
                continue
            if not isinstance(vec, list):
                logger.warning("Vector for %s is not a list — skipping", sym_id)
                continue
            if len(vec) != dimensions:
                logger.warning(
                    "Vector for %s has %d dimensions (expected %d) — skipping",
                    sym_id,
                    len(vec),
                    dimensions,
                )
                continue
            if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vec):
                logger.warning("Vector for %s contains non-finite values — skipping", sym_id)
                continue
            self._vectors[sym_id] = vec

    @staticmethod
    def _decompress_limited(path: Path) -> bytes:
        """Decompress gzip with a size cap to prevent zip-bomb DoS."""
        with open(path, "rb") as fh:
            decompressor = gzip.GzipFile(fileobj=fh)
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = decompressor.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_DECOMPRESSED_SIZE:
                    raise ValueError(f"Decompressed size exceeds {_MAX_DECOMPRESSED_SIZE} bytes")
                chunks.append(chunk)
        return b"".join(chunks)

    def _atomic_write_bytes(self, final_path: Path, data: bytes) -> None:
        """Write *data* to *final_path* atomically via a temp file.

        Uses ``O_NOFOLLOW`` to avoid symlink attacks and cleans up the
        temp file on any failure.
        """
        final_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = final_path.with_name(
            f"{final_path.name}.tmp.{os.getpid()}.{threading.get_ident()}"
        )
        try:
            fd = os.open(
                str(tmp_path),
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            tmp_path.replace(final_path)
        except OSError:
            tmp_path.unlink(missing_ok=True)
            raise
