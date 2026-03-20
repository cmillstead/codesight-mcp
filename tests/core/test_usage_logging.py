"""Tests for UsageRecord and UsageLogger."""

import json
import os
import threading
import time

import pytest

from codesight_mcp.core.usage_logging import UsageLogger, UsageRecord


# ---------------------------------------------------------------------------
# TestUsageRecord
# ---------------------------------------------------------------------------

class TestUsageRecord:
    def test_create_success_record(self):
        rec = UsageRecord(
            tool_name="index_repo",
            timestamp=1000.0,
            success=True,
            error_message=None,
            response_time_ms=150,
            argument_keys=["repo", "branch"],
        )
        assert rec.tool_name == "index_repo"
        assert rec.timestamp == 1000.0
        assert rec.success is True
        assert rec.error_message is None
        assert rec.response_time_ms == 150
        assert rec.argument_keys == ["repo", "branch"]

    def test_create_error_record(self):
        rec = UsageRecord(
            tool_name="get_symbol",
            timestamp=2000.0,
            success=False,
            error_message="Symbol not found",
            response_time_ms=30,
            argument_keys=["symbol_id"],
        )
        assert rec.success is False
        assert rec.error_message == "Symbol not found"

    def test_response_time_rounded_to_10ms_buckets(self):
        rec = UsageRecord(
            tool_name="search_text",
            timestamp=1000.0,
            success=True,
            error_message=None,
            response_time_ms=127,
            argument_keys=[],
        )
        assert rec.response_time_ms == 130

    def test_response_time_rounding_edge_cases(self):
        cases = [(0, 0), (5, 10), (10, 10), (15, 20)]
        for raw, expected in cases:
            rec = UsageRecord(
                tool_name="t",
                timestamp=0.0,
                success=True,
                error_message=None,
                response_time_ms=raw,
                argument_keys=[],
            )
            assert rec.response_time_ms == expected, f"{raw} should round to {expected}"

    def test_to_dict(self):
        rec = UsageRecord(
            tool_name="index_repo",
            timestamp=1000.0,
            success=True,
            error_message=None,
            response_time_ms=130,
            argument_keys=["repo"],
        )
        d = rec.to_dict()
        assert d == {
            "tool_name": "index_repo",
            "timestamp": 1000.0,
            "success": True,
            "error_message": None,
            "response_time_ms": 130,
            "argument_keys": ["repo"],
        }

    def test_from_dict(self):
        original = UsageRecord(
            tool_name="get_callers",
            timestamp=5000.0,
            success=False,
            error_message="timeout",
            response_time_ms=250,
            argument_keys=["symbol_id"],
        )
        d = original.to_dict()
        restored = UsageRecord.from_dict(d)
        assert restored == original


# ---------------------------------------------------------------------------
# TestUsageLoggerMemory
# ---------------------------------------------------------------------------

class TestUsageLoggerMemory:
    def _make_record(self, tool_name: str = "test_tool", success: bool = True,
                     response_time_ms: int = 100, timestamp: float | None = None) -> UsageRecord:
        return UsageRecord(
            tool_name=tool_name,
            timestamp=timestamp or time.time(),
            success=success,
            error_message=None if success else "err",
            response_time_ms=response_time_ms,
            argument_keys=[],
        )

    def test_record_and_get_records(self):
        logger = UsageLogger()
        rec = self._make_record()
        logger.record(rec)
        records = logger.get_records()
        assert len(records) == 1
        assert records[0] == rec

    def test_get_records_returns_copy(self):
        logger = UsageLogger()
        logger.record(self._make_record())
        r1 = logger.get_records()
        r2 = logger.get_records()
        assert r1 is not r2
        assert r1 == r2

    def test_eviction_at_max_memory(self):
        logger = UsageLogger(max_memory=10)
        records = []
        for i in range(11):
            rec = self._make_record(timestamp=float(i))
            records.append(rec)
            logger.record(rec)
        remaining = logger.get_records()
        # 20% of 10 = 2 evicted, so 9 remain
        assert len(remaining) == 9
        # Oldest 2 should be gone
        assert records[0] not in remaining
        assert records[1] not in remaining
        # The 11th record should be present
        assert records[10] in remaining

    def test_eviction_minimum_one(self):
        logger = UsageLogger(max_memory=1)
        logger.record(self._make_record(timestamp=1.0))
        logger.record(self._make_record(timestamp=2.0))
        remaining = logger.get_records()
        # max=1, 20% of 1 = 0.2, min 1 evicted → 1 remains
        assert len(remaining) == 1
        assert remaining[0].timestamp == 2.0

    def test_get_records_filtered_by_tool(self):
        logger = UsageLogger()
        logger.record(self._make_record(tool_name="alpha"))
        logger.record(self._make_record(tool_name="beta"))
        logger.record(self._make_record(tool_name="alpha"))
        assert len(logger.get_records(tool_name="alpha")) == 2
        assert len(logger.get_records(tool_name="beta")) == 1
        assert len(logger.get_records(tool_name="gamma")) == 0

    def test_get_stats_summary(self):
        logger = UsageLogger()
        logger.record(self._make_record(tool_name="a", success=True, response_time_ms=100))
        logger.record(self._make_record(tool_name="a", success=True, response_time_ms=200))
        logger.record(self._make_record(tool_name="a", success=False, response_time_ms=50))
        logger.record(self._make_record(tool_name="b", success=True, response_time_ms=300))

        stats = logger.get_stats()
        assert stats["a"]["total_calls"] == 3
        assert stats["a"]["success_count"] == 2
        assert stats["a"]["error_count"] == 1
        # avg of 100, 200, 50 = 116.67 → but these get rounded to 100, 200, 50 by bucket
        assert stats["a"]["avg_response_time_ms"] == pytest.approx(
            (100 + 200 + 50) / 3, abs=1
        )
        assert stats["b"]["total_calls"] == 1
        assert stats["b"]["success_count"] == 1
        assert stats["b"]["error_count"] == 0

    def test_thread_safety(self):
        logger = UsageLogger(max_memory=10_000)
        errors: list[Exception] = []

        def worker():
            try:
                for _ in range(100):
                    logger.record(self._make_record())
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(logger.get_records()) == 500

    def test_disabled_logger_no_op(self):
        logger = UsageLogger(enabled=False)
        logger.record(self._make_record())
        assert len(logger.get_records()) == 0


# ---------------------------------------------------------------------------
# TestUsageLoggerFile
# ---------------------------------------------------------------------------

class TestUsageLoggerFile:
    def _make_record(self, tool_name: str = "test_tool", success: bool = True,
                     response_time_ms: int = 100, timestamp: float | None = None) -> UsageRecord:
        return UsageRecord(
            tool_name=tool_name,
            timestamp=timestamp or time.time(),
            success=success,
            error_message=None if success else "err",
            response_time_ms=response_time_ms,
            argument_keys=[],
        )

    def test_writes_jsonl_to_disk(self, tmp_path):
        log_file = tmp_path / "usage.jsonl"
        logger = UsageLogger(log_path=str(log_file))
        logger.record(self._make_record(tool_name="alpha", timestamp=1.0))
        logger.record(self._make_record(tool_name="beta", timestamp=2.0))
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["tool_name"] == "alpha"
        second = json.loads(lines[1])
        assert second["tool_name"] == "beta"

    def test_file_created_with_0o600_permissions(self, tmp_path):
        log_file = tmp_path / "usage.jsonl"
        logger = UsageLogger(log_path=str(log_file))
        logger.record(self._make_record())
        assert log_file.stat().st_mode & 0o777 == 0o600

    def test_parent_dir_created_with_0o700(self, tmp_path):
        subdir = tmp_path / "logs" / "deep"
        log_file = subdir / "usage.jsonl"
        logger = UsageLogger(log_path=str(log_file))
        logger.record(self._make_record())
        assert subdir.stat().st_mode & 0o777 == 0o700

    def test_file_rotation_at_50mb(self, tmp_path):
        log_file = tmp_path / "usage.jsonl"
        # Pre-create a file larger than 50MB
        log_file.write_bytes(b"x" * (50 * 1024 * 1024 + 1))
        os.chmod(str(log_file), 0o600)
        logger = UsageLogger(log_path=str(log_file))
        logger.record(self._make_record(tool_name="after_rotate"))
        rotated = tmp_path / "usage.jsonl.1"
        assert rotated.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["tool_name"] == "after_rotate"

    def test_symlink_log_path_rejected(self, tmp_path):
        real_file = tmp_path / "real.jsonl"
        real_file.write_text("")
        link = tmp_path / "link.jsonl"
        link.symlink_to(real_file)
        logger = UsageLogger(log_path=str(link))
        logger.record(self._make_record())
        # Real file should remain empty — symlink rejected by O_NOFOLLOW
        assert real_file.read_text() == ""

    def test_file_write_failure_does_not_break_memory_logging(self, tmp_path):
        # Use a directory as the log path — os.open will fail
        bad_path = tmp_path / "a_dir"
        bad_path.mkdir()
        logger = UsageLogger(log_path=str(bad_path))
        logger.record(self._make_record())
        assert len(logger.get_records()) == 1
