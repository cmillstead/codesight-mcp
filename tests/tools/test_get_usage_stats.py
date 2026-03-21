"""Tests for get_usage_stats tool."""

import json

from codesight_mcp.core.usage_logging import UsageLogger, UsageRecord
from codesight_mcp.tools.get_usage_stats import get_usage_stats


class TestGetUsageStats:
    def _make_logger(self, records=None):
        logger = UsageLogger(max_memory=1000, log_path=None)
        for rec in records or []:
            logger.record(rec)
        return logger

    def test_returns_empty_stats(self):
        logger = self._make_logger()
        all_tools = ["a", "b", "c"]
        result = get_usage_stats(logger=logger, all_tool_names=all_tools)
        assert result["total_calls"] == 0
        assert result["per_tool"] == {}
        assert sorted(result["uncalled_tools"]) == ["a", "b", "c"]

    def test_returns_per_tool_stats(self):
        records = [
            UsageRecord(tool_name="a", timestamp=1.0, success=True, error_message=None, response_time_ms=100),
            UsageRecord(tool_name="a", timestamp=2.0, success=False, error_message="err", response_time_ms=200),
            UsageRecord(tool_name="b", timestamp=3.0, success=True, error_message=None, response_time_ms=50),
        ]
        logger = self._make_logger(records)
        all_tools = ["a", "b", "c"]
        result = get_usage_stats(logger=logger, all_tool_names=all_tools)
        assert result["total_calls"] == 3
        assert result["per_tool"]["a"]["total_calls"] == 2
        assert result["per_tool"]["a"]["success_count"] == 1
        assert result["per_tool"]["a"]["error_count"] == 1
        assert result["per_tool"]["b"]["total_calls"] == 1
        assert result["uncalled_tools"] == ["c"]

    def test_get_usage_stats_excluded_from_uncalled(self):
        logger = self._make_logger()
        all_tools = ["a", "get_usage_stats", "b"]
        result = get_usage_stats(logger=logger, all_tool_names=all_tools)
        assert "get_usage_stats" not in result["uncalled_tools"]
        assert sorted(result["uncalled_tools"]) == ["a", "b"]

    def test_meta_envelope(self):
        logger = self._make_logger()
        result = get_usage_stats(logger=logger, all_tool_names=[])
        meta = result["_meta"]
        assert meta["source"] == "usage_stats"
        assert meta["contentTrust"] == "trusted"
        assert "timing_ms" in meta

    def test_filter_by_tool_name(self):
        records = [
            UsageRecord(tool_name="a", timestamp=1.0, success=True, error_message=None, response_time_ms=100),
            UsageRecord(tool_name="b", timestamp=2.0, success=True, error_message=None, response_time_ms=200),
        ]
        logger = self._make_logger(records)
        all_tools = ["a", "b", "c"]
        result = get_usage_stats(logger=logger, all_tool_names=all_tools, tool_name="a")
        assert "a" in result["per_tool"]
        assert "b" not in result["per_tool"]
        assert result["total_calls"] == 1

    def test_filter_by_tool_name_uncalled_uses_full_history(self):
        """uncalled_tools should reflect ALL calls, not just the filtered tool."""
        records = [
            UsageRecord(tool_name="a", timestamp=1.0, success=True, error_message=None, response_time_ms=100),
            UsageRecord(tool_name="b", timestamp=2.0, success=True, error_message=None, response_time_ms=200),
        ]
        logger = self._make_logger(records)
        all_tools = ["a", "b", "c"]
        result = get_usage_stats(logger=logger, all_tool_names=all_tools, tool_name="a")
        # "b" was called — it should NOT be in uncalled even though we filtered to "a"
        assert "b" not in result["uncalled_tools"]
        assert result["uncalled_tools"] == ["c"]

    def test_session_filter_current_default(self):
        """Default session filter returns only current session records and includes session_id."""
        logger = UsageLogger(max_memory=1000, log_path=None)
        rec = UsageRecord(tool_name="a", timestamp=1.0, success=True, error_message=None, response_time_ms=100)
        logger.record(rec)
        result = get_usage_stats(logger=logger, all_tool_names=["a", "b"])
        assert result["total_calls"] == 1
        assert "session_id" in result
        assert result["session_id"] == logger._session_id

    def test_session_filter_all(self, tmp_path):
        """session='all' returns records from all sessions."""
        log_file = tmp_path / "usage.jsonl"
        # Write an old session record directly to the file
        old_record = {
            "tool_name": "a",
            "timestamp": 1.0,
            "success": True,
            "error_message": None,
            "response_time_ms": 100,
            "argument_keys": [],
            "session_id": "old-session-123",
        }
        log_file.write_text(json.dumps(old_record) + "\n")

        # Create a new logger that will read from the same file
        logger = UsageLogger(max_memory=1000, log_path=str(log_file))
        new_rec = UsageRecord(tool_name="b", timestamp=2.0, success=True, error_message=None, response_time_ms=50)
        logger.record(new_rec)

        result = get_usage_stats(logger=logger, all_tool_names=["a", "b"], session="all")
        assert result["total_calls"] == 2
        assert result["session_id"] == "all"

    def test_session_filter_specific_id(self, tmp_path):
        """Filtering by a specific session_id returns only matching records."""
        log_file = tmp_path / "usage.jsonl"
        target_sid = "target-session-42"
        other_sid = "other-session-99"
        lines = []
        for sid, tool in [(target_sid, "a"), (target_sid, "b"), (other_sid, "c")]:
            lines.append(json.dumps({
                "tool_name": tool,
                "timestamp": 1.0,
                "success": True,
                "error_message": None,
                "response_time_ms": 100,
                "argument_keys": [],
                "session_id": sid,
            }))
        log_file.write_text("\n".join(lines) + "\n")

        logger = UsageLogger(max_memory=1000, log_path=str(log_file))
        result = get_usage_stats(logger=logger, all_tool_names=["a", "b", "c"], session=target_sid)
        assert result["total_calls"] == 2
        assert set(result["per_tool"].keys()) == {"a", "b"}
        assert result["session_id"] == target_sid

    def test_session_filter_current_returns_session_id_in_response(self):
        """Response includes session_id matching logger._session_id when session='current'."""
        logger = UsageLogger(max_memory=1000, log_path=None)
        rec = UsageRecord(tool_name="x", timestamp=1.0, success=True, error_message=None, response_time_ms=10)
        logger.record(rec)
        result = get_usage_stats(logger=logger, all_tool_names=["x"], session="current")
        assert result["session_id"] == logger._session_id
