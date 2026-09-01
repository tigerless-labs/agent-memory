"""Injectable time. Tests assert on relationships, which requires time to be a parameter."""

from __future__ import annotations

import datetime as dt


class Clock:
    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC)

    def today(self) -> str:
        return self.now().date().isoformat()

    def stamp(self) -> str:
        return self.now().strftime("%Y%m%dT%H%M%S%f")


class FrozenClock(Clock):
    def __init__(self, moment: dt.datetime):
        self._moment = moment

    def now(self) -> dt.datetime:
        return self._moment

    def advance(self, **delta: float) -> None:
        self._moment = self._moment + dt.timedelta(**delta)
