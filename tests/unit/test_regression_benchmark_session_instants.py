import pytest
from agent_memory.core.timestamp import parse
from agent_memory.harness.dataset import session_stamp


@pytest.mark.parametrize(
    "date,expected",
    [
        ("2026-01-05T09:12:34Z", "2026-01-05T09:12:34Z"),
        ("2026-01-05T11:12:34+02:00", "2026-01-05T09:12:34Z"),
        ("2026/01/05 (Mon) 09:12:34", "2026-01-05T09:12:34Z"),
    ],
)
def test_benchmark_dates_keep_evidence_instant(date, expected):
    stamp = session_stamp(date)
    assert stamp
    assert parse(stamp) == parse(expected)
