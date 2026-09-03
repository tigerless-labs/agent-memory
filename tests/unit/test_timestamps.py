import datetime as dt

import pytest
from agent_memory.core import timestamp
from agent_memory.core.clock import FrozenClock
from agent_memory.core.errors import ValidationError
from agent_memory.core.manage import ACTION_DATE_NORMALISED, Manage
from agent_memory.core.recall import Recall
from agent_memory.core.record import MemoryRecord
from agent_memory.core.store import Store

TOKYO = dt.timezone(dt.timedelta(hours=9))
DENVER = dt.timezone(dt.timedelta(hours=-7))


def test_render_and_parse_round_trip_to_the_same_instant_in_utc():
    moment = dt.datetime(2026, 1, 15, 17, 0, 42, 123456, tzinfo=TOKYO)
    text = timestamp.render(moment)
    assert text.endswith(timestamp.UTC_SUFFIX)
    assert timestamp.parse(text) == moment.replace(microsecond=0)
    assert timestamp.parse(text).tzinfo == dt.UTC


def test_the_same_instant_renders_identically_from_any_offset():
    instant = dt.datetime(2026, 1, 15, 8, 0, tzinfo=dt.UTC)
    assert timestamp.render(instant.astimezone(TOKYO)) == timestamp.render(
        instant.astimezone(DENVER)
    )


def test_a_calendar_day_parses_as_utc_midnight():
    assert timestamp.parse("2026-01-15") == dt.datetime(2026, 1, 15, tzinfo=dt.UTC)


@pytest.mark.parametrize(
    "payload",
    [
        "2026-01-15T09:00:00",
        "not-a-date",
        "2026-13-01",
        "2026-01-15T09:00:00Z\nstatus: retired",
        "'; DROP TABLE records; --",
        "",
    ],
)
def test_naive_or_malformed_values_are_not_instants(payload):
    assert not timestamp.is_valid(payload)
    with pytest.raises(ValueError):
        timestamp.parse(payload)


def test_rendering_a_naive_datetime_is_refused():
    with pytest.raises(ValueError):
        timestamp.render(dt.datetime(2026, 1, 15, 9, 0))


def test_a_store_writes_the_same_utc_instant_whatever_offset_its_clock_reports(tmp_path, config):
    local = dt.datetime(2026, 1, 15, 17, 0, tzinfo=TOKYO)
    store = Store(tmp_path / "store", config=config, clock=FrozenClock(local), agent="test-agent")
    store.init()
    written = store.record(
        abstract="Tea is served at five", type="fact", domain="user", name="tea"
    )
    assert written.created == written.updated == written.valid_from
    assert written.updated.endswith(timestamp.UTC_SUFFIX)
    assert dt.datetime.fromisoformat(written.updated) == local
    on_disk = MemoryRecord.from_text(
        written.path.read_text(encoding="utf-8"), "user", written.path
    )
    assert on_disk.updated == written.updated


def test_a_calendar_day_valid_from_is_accepted_and_stored_as_utc_midnight(store):
    written = store.record(
        abstract="Worn the sneakers four times", type="fact", domain="user",
        name="sneakers-four", valid_from="2023-05-30",
    )
    assert dt.datetime.fromisoformat(written.valid_from) == dt.datetime(2023, 5, 30, tzinfo=dt.UTC)
    on_disk = MemoryRecord.from_text(
        written.path.read_text(encoding="utf-8"), "user", written.path
    )
    assert on_disk.valid_from == written.valid_from


def test_a_foreign_offset_valid_from_is_stored_in_utc(store):
    given = "2023-05-30T18:00:00+09:00"
    written = store.record(
        abstract="Worn the sneakers four times", type="fact", domain="user",
        name="sneakers-four", valid_from=given,
    )
    assert written.valid_from.endswith(timestamp.UTC_SUFFIX)
    assert dt.datetime.fromisoformat(written.valid_from) == dt.datetime.fromisoformat(given)


@pytest.mark.parametrize(
    "payload",
    [
        "2023-05-30T09:00:00",
        "not-a-date",
        "2026-13-01",
        "2026-01-15T09:00:00Z\nstatus: retired",
        "'; DROP TABLE records; --",
    ],
)
def test_a_valid_from_without_a_zone_or_without_a_shape_is_rejected(store, payload):
    with pytest.raises(ValidationError) as raised:
        store.record(
            abstract="Worn the sneakers four times", type="fact", domain="user",
            name="sneakers-four", valid_from=payload,
        )
    assert "valid_from" in {error.field for error in raised.value.errors}


def test_a_legacy_file_on_disk_is_still_indexed_and_upgraded_when_next_written(seeded):
    target = seeded.find("file-truth-invariant")
    target.created = "2026-01-10"
    target.path.write_text(target.to_text(), encoding="utf-8")
    seeded.sync_index()
    assert seeded.find("file-truth-invariant") is not None
    corrected = seeded.correct("file-truth-invariant", abstract="Markdown files are the truth")
    assert dt.datetime.fromisoformat(corrected.created) == dt.datetime(2026, 1, 10, tzinfo=dt.UTC)
    assert corrected.created.endswith(timestamp.UTC_SUFFIX)


def test_manage_upgrades_calendar_days_and_foreign_offsets_to_utc_instants(seeded):
    target = seeded.find("file-truth-invariant")
    foreign = "2026-01-15T17:30:00+08:00"
    target.created = "2026-01-10"
    target.updated = foreign
    target.path.write_text(target.to_text(), encoding="utf-8")
    seeded.sync_index()

    report = Manage(seeded).sleep()

    after = seeded.find("file-truth-invariant")
    assert dt.datetime.fromisoformat(after.created) == dt.datetime(2026, 1, 10, tzinfo=dt.UTC)
    assert dt.datetime.fromisoformat(after.updated) == dt.datetime.fromisoformat(foreign)
    assert after.created.endswith(timestamp.UTC_SUFFIX)
    assert after.updated.endswith(timestamp.UTC_SUFFIX)
    assert any(
        action.kind == ACTION_DATE_NORMALISED and action.target == target.name
        for action in report.actions
    )


def test_a_canonical_store_gives_manage_nothing_to_normalise(seeded):
    report = Manage(seeded).sleep()
    assert not [action for action in report.actions if action.kind == ACTION_DATE_NORMALISED]


def test_two_facts_from_one_day_are_told_apart_by_the_hour(store):
    store.record(
        abstract="Worn the new sneakers four times", type="fact", domain="user",
        name="sneakers-four", valid_from="2023-05-30T09:00:00Z",
    )
    store.record(
        abstract="Worn the new sneakers six times", type="fact", domain="user",
        name="sneakers-six", valid_from="2023-05-30T18:00:00Z", supersedes="sneakers-four",
    )
    recall = Recall(store)
    noon = {hit.name for hit in recall.recall("sneakers worn", as_of="2023-05-30T12:00:00Z")}
    night = {hit.name for hit in recall.recall("sneakers worn", as_of="2023-05-30T21:00:00Z")}
    assert "sneakers-four" in noon and "sneakers-six" not in noon
    assert "sneakers-six" in night and "sneakers-four" not in night


def test_as_of_in_a_foreign_offset_means_the_same_instant(store):
    store.record(
        abstract="Worn the new sneakers four times", type="fact", domain="user",
        name="sneakers-four", valid_from="2023-05-30T09:00:00Z",
    )
    store.record(
        abstract="Worn the new sneakers six times", type="fact", domain="user",
        name="sneakers-six", valid_from="2023-05-30T18:00:00Z", supersedes="sneakers-four",
    )
    recall = Recall(store)
    utc_noon = {hit.name for hit in recall.recall("sneakers worn", as_of="2023-05-30T12:00:00Z")}
    tokyo_nine_pm = {
        hit.name for hit in recall.recall("sneakers worn", as_of="2023-05-30T21:00:00+09:00")
    }
    assert utc_noon == tokyo_nine_pm


def test_correcting_moves_updated_by_the_clock_not_the_calendar(seeded, clock):
    before = seeded.find("ryan-prefers-concise-answers").updated
    clock.advance(minutes=5)
    after = seeded.correct("ryan-prefers-concise-answers", abstract="Ryan prefers terse answers")
    assert dt.datetime.fromisoformat(after.updated) - dt.datetime.fromisoformat(before) == (
        dt.timedelta(minutes=5)
    )
