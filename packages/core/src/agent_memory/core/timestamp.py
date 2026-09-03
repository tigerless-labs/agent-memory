"""Every date field is one aware instant rendered in UTC. Host time zones stay out of the files."""

from __future__ import annotations

import datetime as dt

UTC_SUFFIX = "Z"
_OFFSET_ZERO = "+00:00"
_SECONDS_PER_DAY = 86400.0


def parse(value: str) -> dt.datetime:
    text = str(value).strip()
    try:
        day = dt.date.fromisoformat(text)
    except ValueError:
        pass
    else:
        return dt.datetime(day.year, day.month, day.day, tzinfo=dt.UTC)
    moment = dt.datetime.fromisoformat(text)
    if moment.utcoffset() is None:
        raise ValueError(f"time zone missing: {text}")
    return moment.astimezone(dt.UTC)


def render(moment: dt.datetime) -> str:
    if moment.utcoffset() is None:
        raise ValueError("time zone missing")
    utc = moment.astimezone(dt.UTC).replace(microsecond=0)
    return utc.isoformat().replace(_OFFSET_ZERO, UTC_SUFFIX)


def canonical(value: str) -> str:
    return render(parse(value))


def days_between(later: dt.datetime, earlier: dt.datetime) -> float:
    return (later - earlier).total_seconds() / _SECONDS_PER_DAY


def is_valid(value: str) -> bool:
    try:
        parse(value)
    except ValueError:
        return False
    return True
