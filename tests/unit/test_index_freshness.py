"""Tests for the shared index-age helper in core/freshness.py.

Covers the ISO parser, the unrounded threshold compare, fail-closed
behavior for unknown/future timestamps, and parity with verify()'s
freshness check (which loads the compressed full index via RepoContext,
not the metadata sidecar).
"""
import gzip
import json
from datetime import datetime, timedelta, timezone

import pytest

from codesight_mcp.core.freshness import (
    INDEX_AGE_THRESHOLD_DAYS,
    age_threshold_exceeded,
    index_age_days,
    parse_indexed_at,
    valid_git_head,
)
from codesight_mcp.tools.verify import verify


# --- parse_indexed_at -------------------------------------------------

def test_parse_indexed_at_handles_z_suffix_without_raising():
    dt = parse_indexed_at("2026-07-01T12:00:00Z")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timedelta(0)


def test_parse_indexed_at_assumes_utc_for_naive_stamp():
    dt = parse_indexed_at("2026-07-01T12:00:00")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timedelta(0)


def test_parse_indexed_at_returns_none_for_unparseable_string():
    assert parse_indexed_at("not-a-timestamp") is None


def test_parse_indexed_at_returns_none_for_non_string():
    assert parse_indexed_at(None) is None
    assert parse_indexed_at(12345) is None


def test_parse_indexed_at_returns_none_instead_of_raising_on_min_year_overflow():
    """An in-range ISO stamp whose UTC conversion underflows MINYEAR must
    fail closed (None), not raise OverflowError -- a crafted sidecar with
    this value must not crash list_repos()/get_status() for every repo."""
    assert parse_indexed_at("0001-01-01T00:30:00+01:00") is None


def test_parse_indexed_at_returns_none_instead_of_raising_on_max_year_overflow():
    """Same fail-closed contract at the MAXYEAR boundary."""
    assert parse_indexed_at("9999-12-31T23:59:00-01:00") is None


def test_index_age_days_fails_closed_on_overflowing_stamp():
    assert index_age_days("0001-01-01T00:30:00+01:00") is None
    assert index_age_days("9999-12-31T23:59:00-01:00") is None


def test_age_threshold_exceeded_fails_closed_on_overflowing_stamp():
    assert age_threshold_exceeded("0001-01-01T00:30:00+01:00") is None
    assert age_threshold_exceeded("9999-12-31T23:59:00-01:00") is None


# --- index_age_days / age_threshold_exceeded ---------------------------

def test_fresh_index_is_not_threshold_exceeded():
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    stamp = (now - timedelta(hours=1)).isoformat()
    assert age_threshold_exceeded(stamp, now=now) is False


def test_backdated_30_days_is_threshold_exceeded():
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    stamp = (now - timedelta(days=30)).isoformat()
    assert age_threshold_exceeded(stamp, now=now) is True
    age = index_age_days(stamp, now=now)
    assert age is not None
    assert 29.9 <= age <= 30.1


def test_future_stamp_beyond_skew_is_unknown_not_fresh_not_exceeded():
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    stamp = (now + timedelta(days=1)).isoformat()
    assert index_age_days(stamp, now=now) is None
    assert age_threshold_exceeded(stamp, now=now) is None


def test_exactly_at_threshold_boundary_is_not_exceeded():
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    stamp = (now - timedelta(days=INDEX_AGE_THRESHOLD_DAYS)).isoformat()
    assert age_threshold_exceeded(stamp, now=now) is False


def test_one_second_past_threshold_boundary_is_exceeded():
    """Proves the compare is on the UNROUNDED age -- 7d+1s must trip True
    even though rounding to whole days would show 7.0."""
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    stamp = (now - timedelta(days=INDEX_AGE_THRESHOLD_DAYS, seconds=1)).isoformat()
    assert age_threshold_exceeded(stamp, now=now) is True


def test_unparseable_string_yields_none_for_both_helpers():
    assert index_age_days("garbage") is None
    assert age_threshold_exceeded("garbage") is None


# --- valid_git_head -----------------------------------------------------

def test_valid_git_head_accepts_short_hex():
    assert valid_git_head("deadbeef") == "deadbeef"


@pytest.mark.parametrize("bad", ["", None, "nothex", "g" * 40, "a" * 64, "ABCDEF1"])
def test_valid_git_head_rejects_malformed_values(bad):
    assert valid_git_head(bad) is None


# --- verify() parity + fail-closed ---------------------------------------

def _mutate_indexed_at(tmp_path, owner: str, name: str, new_value) -> None:
    """Rewrite the compressed FULL index's indexed_at field on disk.

    verify() loads the index itself via RepoContext (not the .meta.json
    sidecar), so the mutation target must be the .json.gz index file.
    """
    index_path = tmp_path / f"{owner}__{name}.json.gz"
    with gzip.open(index_path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    data["indexed_at"] = new_value
    with gzip.open(index_path, "wt", encoding="utf-8") as f:
        json.dump(data, f)


def test_verify_freshness_fails_for_backdated_index(python_index, tmp_path):
    old_stamp = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    _mutate_indexed_at(tmp_path, python_index["owner"], python_index["name"], old_stamp)

    result = verify(
        repo=f"{python_index['owner']}/{python_index['name']}",
        storage_path=str(tmp_path),
    )
    assert result["checks"]["freshness"]["passed"] is False
    assert result["passed"] is False


def test_verify_freshness_fails_closed_for_z_suffixed_backdated_index(python_index, tmp_path):
    old_stamp = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    _mutate_indexed_at(tmp_path, python_index["owner"], python_index["name"], old_stamp)

    result = verify(
        repo=f"{python_index['owner']}/{python_index['name']}",
        storage_path=str(tmp_path),
    )
    assert result["checks"]["freshness"]["passed"] is False


def test_verify_freshness_fails_closed_for_future_index(python_index, tmp_path):
    future_stamp = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    _mutate_indexed_at(tmp_path, python_index["owner"], python_index["name"], future_stamp)

    result = verify(
        repo=f"{python_index['owner']}/{python_index['name']}",
        storage_path=str(tmp_path),
    )
    assert result["checks"]["freshness"]["passed"] is False


def test_verify_freshness_derives_default_max_age_from_shared_threshold(python_index, tmp_path):
    result = verify(
        repo=f"{python_index['owner']}/{python_index['name']}",
        storage_path=str(tmp_path),
    )
    assert result["checks"]["freshness"]["max_age_hours"] == INDEX_AGE_THRESHOLD_DAYS * 24
