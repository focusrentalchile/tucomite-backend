"""License window rules for building clients."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

LICENSE_WARN_DAYS = 2
LICENSE_GRACE_DAYS = 5


@dataclass(frozen=True)
class LicenseEvaluation:
    """Computed license state for a signed-in building user."""

    status: str
    starts_at: str | None
    ends_at: str | None
    days_remaining: int | None


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def evaluate_license(
    starts_at: str | None,
    ends_at: str | None,
    *,
    today: date | None = None,
) -> LicenseEvaluation:
    """Classify a license as active, expiring, grace, or inactive."""
    current = today or date.today()
    start = _parse_day(starts_at)
    end = _parse_day(ends_at)
    if start is None or end is None:
        return LicenseEvaluation(status="inactive", starts_at=starts_at, ends_at=ends_at, days_remaining=None)
    if end < start:
        return LicenseEvaluation(
            status="inactive",
            starts_at=start.isoformat(),
            ends_at=end.isoformat(),
            days_remaining=None,
        )
    if current < start:
        return LicenseEvaluation(
            status="inactive",
            starts_at=start.isoformat(),
            ends_at=end.isoformat(),
            days_remaining=None,
        )
    if current <= end:
        remaining = (end - current).days
        status = "expiring" if remaining <= LICENSE_WARN_DAYS else "active"
        return LicenseEvaluation(
            status=status,
            starts_at=start.isoformat(),
            ends_at=end.isoformat(),
            days_remaining=remaining,
        )
    grace_end = end + timedelta(days=LICENSE_GRACE_DAYS)
    if current <= grace_end:
        return LicenseEvaluation(
            status="grace",
            starts_at=start.isoformat(),
            ends_at=end.isoformat(),
            days_remaining=(grace_end - current).days,
        )
    return LicenseEvaluation(
        status="inactive",
        starts_at=start.isoformat(),
        ends_at=end.isoformat(),
        days_remaining=None,
    )


def utc_today() -> date:
    """Return today's calendar date in UTC for stable tests."""
    return datetime.utcnow().date()
