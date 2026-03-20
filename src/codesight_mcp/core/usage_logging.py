"""Usage logging for MCP tool invocations."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .locking import ensure_private_dir

_MAX_LOG_BYTES = 50 * 1024 * 1024


@dataclass
class UsageRecord:
    """A single tool invocation record."""

    tool_name: str
    timestamp: float
    success: bool
    error_message: str | None
    response_time_ms: int
    argument_keys: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.response_time_ms = (self.response_time_ms + 5) // 10 * 10

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "timestamp": self.timestamp,
            "success": self.success,
            "error_message": self.error_message,
            "response_time_ms": self.response_time_ms,
            "argument_keys": list(self.argument_keys),
        }

    @classmethod
    def from_dict(cls, data: dict) -> UsageRecord:
        return cls(
            tool_name=data["tool_name"],
            timestamp=data["timestamp"],
            success=data["success"],
            error_message=data["error_message"],
            response_time_ms=data["response_time_ms"],
            argument_keys=data["argument_keys"],
        )


class UsageLogger:
    """In-memory usage logger with optional eviction."""

    def __init__(
        self,
        max_memory: int = 10_000,
        log_path: str | None = None,
        enabled: bool = True,
    ) -> None:
        self._records: list[UsageRecord] = []
        self._lock = threading.Lock()
        self._max_memory = max_memory
        self._log_path = Path(log_path) if log_path else None
        self._enabled = enabled

    def record(self, rec: UsageRecord) -> None:
        """Append a record. Silently catches all exceptions."""
        if not self._enabled:
            return
        try:
            with self._lock:
                self._records.append(rec)
                if len(self._records) > self._max_memory:
                    evict_count = max(1, int(self._max_memory * 0.2))
                    self._records = self._records[evict_count:]
        except Exception:
            pass
        try:
            self._write_to_file(rec)
        except Exception:
            pass

    def _write_to_file(self, rec: UsageRecord) -> None:
        """Write a record as JSONL to the log file."""
        if self._log_path is None:
            return
        path = self._log_path
        ensure_private_dir(path.parent)
        # Rotate if file exceeds size limit
        if path.exists() and not path.is_symlink():
            try:
                if path.stat().st_size > _MAX_LOG_BYTES:
                    rotated = path.with_name(path.name + ".1")
                    if rotated.exists():
                        rotated.unlink()
                    path.rename(rotated)
            except OSError:
                pass
        data_bytes = (json.dumps(rec.to_dict()) + "\n").encode()
        fd = os.open(
            str(path),
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
            0o600,
        )
        try:
            os.write(fd, data_bytes)
        finally:
            os.close(fd)

    def get_records(self, tool_name: str | None = None) -> list[UsageRecord]:
        """Return a copy of records, optionally filtered by tool_name."""
        with self._lock:
            if tool_name is not None:
                return [r for r in self._records if r.tool_name == tool_name]
            return list(self._records)

    def get_stats(self) -> dict:
        """Return per-tool stats: total_calls, success_count, error_count, avg_response_time_ms."""
        with self._lock:
            records = list(self._records)

        stats: dict[str, dict] = {}
        for rec in records:
            if rec.tool_name not in stats:
                stats[rec.tool_name] = {
                    "total_calls": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "_total_ms": 0,
                }
            s = stats[rec.tool_name]
            s["total_calls"] += 1
            if rec.success:
                s["success_count"] += 1
            else:
                s["error_count"] += 1
            s["_total_ms"] += rec.response_time_ms

        for s in stats.values():
            s["avg_response_time_ms"] = round(
                s.pop("_total_ms") / s["total_calls"], 1
            )

        return stats
