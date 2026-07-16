"""Tests for the aggregate staleness surface added to get_status().

get_status is a TRUSTED envelope: it must report aged-repo counts without
leaking any attacker-influenceable repo-name string into the response.
"""
import gzip
import json
from datetime import datetime, timedelta, timezone

from codesight_mcp.tools import _common
from codesight_mcp.tools.get_status import get_status


def _backdate_repo(tmp_path, owner: str, name: str, days: int) -> None:
    """Backdate both the metadata sidecar and full index's indexed_at.

    list_repos() prefers the sidecar (Phase 1) but falls back to the full
    index (Phase 2) when no sidecar is present -- backdating both keeps
    this test independent of which branch is exercised.
    """
    old_stamp = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    meta_path = tmp_path / f"{owner}__{name}.meta.json"
    meta = json.loads(meta_path.read_text())
    meta["indexed_at"] = old_stamp
    meta_path.write_text(json.dumps(meta))

    index_path = tmp_path / f"{owner}__{name}.json.gz"
    with gzip.open(index_path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    data["indexed_at"] = old_stamp
    with gzip.open(index_path, "wt", encoding="utf-8") as f:
        json.dump(data, f)


def test_get_status_reports_aged_repo_count_for_backdated_repo(python_index, tmp_path):
    _common._clear_shared_stores()
    _backdate_repo(tmp_path, python_index["owner"], python_index["name"], days=30)

    result = get_status(storage_path=str(tmp_path))

    assert result["aged_repo_count"] == 1
    assert "oldest_index_age_days" in result
    assert result["oldest_index_age_days"] >= 29.9
    assert "index-folder --path" in result["staleness_warning"]


def test_get_status_response_contains_no_repo_name_strings(python_index, tmp_path):
    _common._clear_shared_stores()
    _backdate_repo(tmp_path, python_index["owner"], python_index["name"], days=30)

    result = get_status(storage_path=str(tmp_path))

    assert "repo" not in result
    serialized = json.dumps(result)
    assert python_index["owner"] not in serialized
    assert f"{python_index['owner']}/{python_index['name']}" not in serialized


def test_get_status_fresh_repo_has_no_staleness_warning(python_index, tmp_path):
    _common._clear_shared_stores()

    result = get_status(storage_path=str(tmp_path))

    assert result["aged_repo_count"] == 0
    assert "staleness_warning" not in result
