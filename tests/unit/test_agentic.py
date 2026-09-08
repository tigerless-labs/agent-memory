"""The executor may look before it writes; the library runs the tools and keeps the rules."""

import json

from agent_memory.core import agentic, distill, prompts, reconcile, sessions

LINES = [
    "user: Our queue timeout is 30 seconds now, we raised it from 20 last Tuesday.",
    "assistant: Noted.",
]


def _messages(store, session="boundary", lines=LINES):
    pointer = store.archive.append_session(session, lines)
    return sessions.resolve(store.layout, pointer)


def _existing(store):
    return store.record(
        type="fact",
        fields={"project": "pipeline", "subject": "queue timeout"},
        abstract="Queue timeout is 20 seconds",
        body="Set in infra/queue.yaml.",
    )


def _scripted(*replies):
    queue = list(replies)

    def ask(prompt):
        ask.prompts.append(prompt)
        return queue.pop(0) if queue else ""

    ask.prompts = []
    return ask


def _call(tool, **fields):
    return json.dumps({agentic.KEY_TOOL: tool, **fields})


def _supersede(handle):
    return json.dumps(
        {
            "type": "fact",
            "op": "supersede",
            "handle": handle,
            "fields": {"project": "pipeline", "subject": "queue timeout 30s"},
            "abstract": "Queue timeout is 30 seconds",
            "provenance": ["0"],
        }
    )


def _empty_sheet(store, messages):
    sheet = reconcile.build(store, "boundary", messages)
    return reconcile.Sheet(
        sheet.session, sheet.pointer, (), sheet.menus, sheet.profile, sheet.slots, sheet.messages
    )


def test_a_recall_round_makes_a_handle_usable_that_the_sheet_did_not_carry(store):
    old = _existing(store)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    ask = _scripted(_call("recall", query="queue timeout"), _supersede(old.name))
    outcome = agentic.negotiate(store, sheet, "opening", ask, store.config.write)
    assert old.name in outcome.sheet.handle_names()
    assert outcome.rounds == 2
    assert reconcile.check(outcome.specs[0], outcome.sheet) == []
    assert old.name in ask.prompts[1]
    assert prompts.TOOL_RULES in ask.prompts[0]


def test_a_read_round_returns_the_body_and_the_transcript_keeps_it(store):
    old = _existing(store)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    ask = _scripted(_call("read", name=old.name), _call("recall", query="anything"), "")
    outcome = agentic.negotiate(store, sheet, "opening", ask, store.config.write)
    assert "infra/queue.yaml" in ask.prompts[1]
    assert "infra/queue.yaml" in ask.prompts[2]
    assert old.name in outcome.sheet.handle_names()


def test_the_round_cap_holds_with_one_extension_for_a_tool_call_on_the_last_round(store):
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    store.config.write.max_rounds = 2
    ask = _scripted(*[_call("recall", query="q")] * 6)
    outcome = agentic.negotiate(store, sheet, "opening", ask, store.config.write)
    assert outcome.rounds == 3
    assert outcome.specs == []
    assert prompts.FINAL_ROUND in ask.prompts[1]
    assert prompts.FINAL_ROUND not in ask.prompts[0]


def test_an_unknown_tool_is_answered_with_the_tool_list_and_the_loop_goes_on(store):
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    ask = _scripted(_call("delete", name="x"), json.dumps({"type": "fact", "op": "skip"}))
    outcome = agentic.negotiate(store, sheet, "opening", ask, store.config.write)
    assert "unknown tool" in ask.prompts[1]
    assert agentic.TOOL_RECALL in ask.prompts[1]
    assert outcome.rounds == 2


def test_a_handle_nobody_has_seen_is_still_refused(store):
    old = _existing(store)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    ask = _scripted(_supersede(old.name))
    outcome = agentic.negotiate(store, sheet, "opening", ask, store.config.write)
    assert "handle" in {error.field for error in reconcile.check(outcome.specs[0], outcome.sheet)}


def test_an_unreadable_reply_gets_one_more_chance_then_counts_as_no_operations(store):
    old = _existing(store)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    ask = _scripted("", _supersede(old.name))
    outcome = agentic.negotiate(store, sheet, "opening", ask, store.config.write)
    assert "could not be read" in ask.prompts[1]
    assert len(outcome.specs) == 1

    ask = _scripted("", "still nothing")
    outcome = agentic.negotiate(store, sheet, "opening", ask, store.config.write)
    assert outcome.specs == []
    assert outcome.rounds == 2


def test_a_long_observation_is_clipped(store):
    store.record(type="fact", fields={"subject": "long"}, abstract="Long body", body="x" * 50)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    store.config.write.tool_result_chars = 40
    ask = _scripted(_call("read", name="long"), "")
    agentic.negotiate(store, sheet, "opening", ask, store.config.write)
    assert "(truncated)" in ask.prompts[1]


def test_distill_runs_the_negotiation_and_reports_the_rounds(store):
    old = _existing(store)
    messages = _messages(store)
    ask = _scripted(_call("recall", query="queue timeout"), _supersede(old.name))
    report = distill.distill(store, "boundary", messages, ask)
    assert report.batches[0].rounds == 2
    assert report.batches[0].written == ("queue-timeout-30s",)
    assert not store.find(old.name).is_active()
