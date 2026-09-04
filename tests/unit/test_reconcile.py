"""The reconciled write: the executor fills a form, and the sheet bounds what the form may do."""

import json

from agent_memory.core import batching, distill, pending, reconcile, render, sessions
from agent_memory.core.recall import Recall
from agent_memory.core.watermark import Watermark

LINES = [
    "user: Our queue timeout is 30 seconds, we set it last Tuesday.",
    "assistant: Noted. Anything else about the deploy pipeline?",
    "user: Yes, we decided to sign every release tag from now on.",
]


def _messages(store, session="boundary", lines=LINES):
    pointer = store.archive.append_session(session, lines)
    return sessions.resolve(store.layout, pointer)


def _spec(**overrides):
    base = {
        "type": "fact",
        "fields": {"project": "pipeline", "subject": "queue timeout"},
        "abstract": "Queue timeout is 30 seconds",
        "provenance": ["0"],
    }
    base.update(overrides)
    return base


def _replies(*batches):
    queue = [
        "\n".join(json.dumps(spec) for spec in batch) if isinstance(batch, list) else batch
        for batch in batches
    ]

    def ask(prompt):
        return queue.pop(0) if queue else ""

    ask.prompts = []
    original = ask

    def recording(prompt):
        recording.prompts.append(prompt)
        return original(prompt)

    recording.prompts = []
    return recording


def test_rendering_numbers_every_message_and_states_the_session_time(store):
    text = render.conversation(_messages(store))
    assert "[0][user]:" in text
    assert "[2][user]:" in text
    assert "Session time:" in text
    assert "2026-01-15" in text


def test_batching_splits_on_message_boundaries_and_never_inside_one(store):
    messages = _messages(store)
    cap = len(LINES[0])
    split = batching.batches(messages, cap)
    assert [len(batch) for batch in split] == [1, 1, 1]
    assert [batch[0].index for batch in split] == [0, 1, 2]
    assert batching.batches(messages, sum(len(line) for line in LINES) * 2) == [messages]


def test_the_sheet_names_related_memories_by_handle_and_lists_group_menus(store):
    store.record(
        type="fact",
        fields={"project": "pipeline", "subject": "queue timeout"},
        abstract="Queue timeout is 20 seconds",
        body="Set in infra/queue.yaml.",
    )
    store.record(
        type="preference",
        fields={"topic": "coffee", "subject": "milk"},
        abstract="Prefers oat milk",
        create_group=True,
    )
    sheet = reconcile.build(store, "boundary", _messages(store))
    assert "queue-timeout" in sheet.handle_names()
    assert "coffee" in sheet.menus["preference"]
    assert "pipeline" in sheet.menus["fact"]
    rendered = sheet.render()
    assert "queue-timeout" in rendered and "coffee" in rendered


def test_building_the_sheet_leaves_no_trace_in_the_access_log(store):
    from agent_memory.core.access_log import AccessLog
    from agent_memory.core.database import Database

    store.record(type="fact", fields={"subject": "queue timeout"}, abstract="Queue timeout 20s")
    reconcile.build(store, "boundary", _messages(store))
    with Database(store.layout).connect() as connection:
        assert AccessLog(connection).entries() == []


def test_an_operation_naming_a_handle_outside_the_sheet_is_refused(store):
    sheet = reconcile.build(store, "boundary", _messages(store))
    errors = reconcile.check(_spec(op="supersede", handle="never-listed"), sheet)
    assert "handle" in {error.field for error in errors}
    assert reconcile.check(_spec(op="new"), sheet) == []


def test_provenance_defaults_to_the_batch_when_the_executor_omits_it(store):
    messages = _messages(store)
    sheet = reconcile.build(store, "boundary", messages)
    spec = reconcile.to_record_spec(_spec(provenance=[]), sheet)
    assert spec["provenance"] == [sessions.render_pointer(sheet.pointer)]
    narrowed = reconcile.to_record_spec(_spec(provenance=["1-2"]), sheet)
    assert narrowed["provenance"] == [sessions.render_pointer(sessions.Pointer("boundary", 1, 2))]


def test_an_undated_memory_is_dated_by_the_messages_it_cites(store):
    messages = _messages(store)
    sheet = reconcile.build(store, "boundary", messages)
    spec = reconcile.to_record_spec(_spec(provenance=["1"]), sheet)
    assert spec["valid_from"] == messages[1].at
    dated = reconcile.to_record_spec(_spec(valid_from="2025-12-01"), sheet)
    assert dated["valid_from"] == "2025-12-01"


def test_a_skip_writes_nothing_and_rejects_nothing(store):
    messages = _messages(store)
    ask = _replies([_spec(op="skip")])
    report = distill.distill(store, "boundary", messages, ask)
    assert report.batches[0].written == ()
    assert report.batches[0].rejected == ()
    assert store.records() == []


def test_distilling_writes_the_form_and_advances_the_watermark_per_batch(store):
    messages = _messages(store)
    store.config.write.max_distill_input_chars = len(LINES[0])
    decision = {
        "type": "decision",
        "fields": {"project": "pipeline", "subject": "signed tags"},
        "abstract": "Every release tag is signed",
        "provenance": ["2"],
    }
    ask = _replies([_spec()], [_spec(op="skip")], [decision])
    report = distill.distill(store, "boundary", messages, ask)
    assert len(report.batches) == 3
    assert report.consumed == len(LINES)
    assert Watermark(store.layout).read("boundary").distilled == len(LINES)
    names = {record.name for record in store.records()}
    assert {"queue-timeout", "signed-tags"} <= names
    assert len(ask.prompts) == 3
    assert "[0][user]" in ask.prompts[0] and "[2][user]" in ask.prompts[2]


def test_a_refused_write_gets_one_repair_round_then_waits_in_pending(store):
    messages = _messages(store)
    bad = _spec(op="supersede", handle="ghost")
    ask = _replies([bad], [bad])
    report = distill.distill(store, "boundary", messages, ask)
    assert report.batches[0].pending == 1
    assert "Refused" in ask.prompts[1]
    queued = pending.Pending(store.layout)
    assert queued.sessions() == ["boundary"]

    ask_again = _replies([_spec()])
    later = distill.distill(store, "boundary", _messages(store, lines=["user: more"]), ask_again)
    assert "ghost" in ask_again.prompts[1]
    assert later.batches[0].written == ("queue-timeout",)
    assert later.batches[0].pending == 1
    assert len(queued.drain("boundary")) == 1


def test_supersede_through_the_form_invalidates_the_handle(store):
    old = store.record(
        type="fact",
        fields={"project": "pipeline", "subject": "queue timeout"},
        abstract="Queue timeout is 20 seconds",
    )
    messages = _messages(store)
    newer = _spec(
        op="supersede",
        handle=old.name,
        fields={"project": "pipeline", "subject": "queue timeout v2"},
    )
    distill.distill(store, "boundary", messages, _replies([newer]))
    assert not store.find(old.name).is_active()
    hits = Recall(store).recall("queue timeout")
    assert [hit.name for hit in hits] == ["queue-timeout-v2"]


def test_the_slot_table_lists_every_type_the_store_knows(store):
    from agent_memory.core import prompts

    table = prompts.slot_table(store.schemas.all())
    for schema in store.schemas.all():
        assert schema.type in table
        assert schema.description.split(".")[0] in table


def test_the_slot_table_and_the_event_lane_are_write_options(store):
    from agent_memory.core import prompts

    messages = _messages(store)
    store.config.write.slot_table = False
    store.config.write.event_lane = False
    ask = _replies([])
    distill.distill(store, "boundary", messages, ask)
    assert prompts.EVENT_LANE not in ask.prompts[0]
    assert prompts.SLOT_INSTRUCTION not in ask.prompts[0]
    for schema in store.schemas.all():
        assert schema.type in ask.prompts[0]

    store.config.write.slot_table = True
    store.config.write.event_lane = True
    ask = _replies([])
    distill.distill(store, "boundary", _messages(store, lines=["user: more"]), ask)
    assert prompts.EVENT_LANE in ask.prompts[0]
    assert prompts.SLOT_INSTRUCTION in ask.prompts[0]


def test_unparseable_reply_lines_are_reported_by_line_number():
    specs, errors = reconcile.parse_operations('```json\n{"type": "fact"}\nnot json\n```')
    assert specs == [{"type": "fact"}]
    assert [error.field for error in errors] == ["line 3"]
