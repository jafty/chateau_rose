from datetime import datetime, time, timedelta

from chateaurose.domain.exceptions import ValidationError

MINIMUM_BOOKING_NOTICE = timedelta(hours=24)
PROCESS_LIFETIME = timedelta(days=6)


def require_minimum_notice(*, desired_at: datetime, now: datetime) -> None:
    if desired_at < now + MINIMUM_BOOKING_NOTICE:
        raise ValidationError(
            "Le rendez-vous doit être demandé au moins 24 heures à l'avance."
        )


def add_response_hours(start: datetime, hours: int) -> datetime:
    """Add hours counted only from 08:00 (inclusive) to 22:00 (exclusive)."""
    current, remaining = start, hours
    while remaining:
        day_start = datetime.combine(current.date(), time(8), tzinfo=current.tzinfo)
        day_end = datetime.combine(current.date(), time(22), tzinfo=current.tzinfo)
        if current < day_start:
            current = day_start
        elif current >= day_end:
            current = day_start + timedelta(days=1)
            continue
        available = (day_end - current).total_seconds() / 3600
        consumed = min(available, remaining)
        current += timedelta(hours=consumed)
        remaining -= consumed
        if remaining:
            current = datetime.combine(
                current.date() + timedelta(days=1), time(8), tzinfo=current.tzinfo
            )
    return current


def initial_provider_deadline(*, now: datetime, desired_at: datetime) -> datetime:
    require_minimum_notice(desired_at=desired_at, now=now)
    return add_response_hours(now, 4 if desired_at < now + timedelta(hours=48) else 12)


def bounded_deadline(
    *, start: datetime, response_hours: int, process_expires_at: datetime
) -> datetime:
    return min(add_response_hours(start, response_hours), process_expires_at)
