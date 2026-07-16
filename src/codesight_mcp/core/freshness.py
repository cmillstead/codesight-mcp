"""Shared index-age policy: one ISO parser + one threshold, used by
tools/verify.py and the get-status / list-repos staleness surface."""
from datetime import datetime, timezone

INDEX_AGE_THRESHOLD_DAYS = 7  # single policy source; verify.py derives its hours from this
_FUTURE_SKEW_DAYS = 1.0 / 24  # tolerate ~1h clock skew; beyond that a future stamp is "unknown"


def parse_indexed_at(value: object) -> datetime | None:
    """Parse an ISO-8601 indexed_at to an aware UTC datetime, or None.
    Handles trailing 'Z' (3.10 fromisoformat does not) and naive stamps
    (assumed UTC). Never raises."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _raw_age_days(value: object, now: datetime | None = None) -> float | None:
    """UNROUNDED age in days, or None if unparseable OR meaningfully in the
    future (beyond clock-skew tolerance). A future stamp is UNKNOWN — never
    'fresh', never 'exceeded'."""
    dt = parse_indexed_at(value)
    if dt is None:
        return None
    ref = now or datetime.now(timezone.utc)
    age = (ref - dt).total_seconds() / 86400.0
    if age < -_FUTURE_SKEW_DAYS:
        return None
    return age


def index_age_days(value: object, *, now: datetime | None = None) -> float | None:
    """Age in days rounded to 2dp for DISPLAY. None if unparseable/future."""
    age = _raw_age_days(value, now=now)
    return None if age is None else round(age, 2)


def age_threshold_exceeded(
    value: object, *, threshold_days: int | float = INDEX_AGE_THRESHOLD_DAYS,
    now: datetime | None = None,
) -> bool | None:
    """True if the UNROUNDED age strictly exceeds threshold (so 7d+1s IS
    exceeded). None if unparseable/future — caller must fail closed."""
    age = _raw_age_days(value, now=now)
    if age is None:
        return None
    return age > threshold_days


def valid_git_head(value: object) -> str | None:
    """Return value if it is a bounded lowercase hex commit id, else None."""
    if isinstance(value, str) and 7 <= len(value) <= 40 and all(c in "0123456789abcdef" for c in value):
        return value
    return None
