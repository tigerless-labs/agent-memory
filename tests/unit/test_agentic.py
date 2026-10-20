"""The executor may look before it writes; the library runs the tools and keeps the rules."""

import json

from agent_memory.core import agentic, distill, prompts, reconcile, sessions, toolkit

BRIEF = prompts.Brief(instructions="instructions", material="material")
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
    outcome = agentic.negotiate(store, sheet, BRIEF, ask, store.config.write)
    assert old.name in outcome.sheet.handle_names()
    assert outcome.rounds == 2
    assert reconcile.check(outcome.specs[0], outcome.sheet) == []
    assert old.name in ask.prompts[1]
    assert prompts.tool_rules(False) in ask.prompts[0]
    assert ask.prompts[0].startswith(BRIEF.text_protocol())


def test_a_read_round_returns_the_body_and_the_transcript_keeps_it(store):
    old = _existing(store)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    ask = _scripted(_call("read", name=old.name), _call("recall", query="anything"), "")
    outcome = agentic.negotiate(store, sheet, BRIEF, ask, store.config.write)
    assert "infra/queue.yaml" in ask.prompts[1]
    assert "infra/queue.yaml" in ask.prompts[2]
    assert old.name in outcome.sheet.handle_names()


def test_the_round_cap_holds_with_one_extension_for_a_tool_call_on_the_last_round(store):
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    store.config.write.max_rounds = 2
    ask = _scripted(*[_call("recall", query="q")] * 6)
    outcome = agentic.negotiate(store, sheet, BRIEF, ask, store.config.write)
    assert outcome.rounds == 3
    assert outcome.specs == []
    assert prompts.FINAL_ROUND in ask.prompts[1]
    assert prompts.FINAL_ROUND not in ask.prompts[0]


def test_an_unknown_tool_is_answered_with_the_tool_list_and_the_loop_goes_on(store):
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    ask = _scripted(_call("delete", name="x"), json.dumps({"type": "fact", "op": "skip"}))
    outcome = agentic.negotiate(store, sheet, BRIEF, ask, store.config.write)
    assert "unknown tool" in ask.prompts[1]
    assert agentic.TOOL_RECALL in ask.prompts[1]
    assert outcome.rounds == 2


def test_a_handle_nobody_has_seen_is_still_refused(store):
    old = _existing(store)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    ask = _scripted(_supersede(old.name))
    outcome = agentic.negotiate(store, sheet, BRIEF, ask, store.config.write)
    assert "handle" in {error.field for error in reconcile.check(outcome.specs[0], outcome.sheet)}


def test_an_unreadable_reply_gets_one_more_chance_then_counts_as_no_operations(store):
    old = _existing(store)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    ask = _scripted("", _supersede(old.name))
    outcome = agentic.negotiate(store, sheet, BRIEF, ask, store.config.write)
    assert "could not be read" in ask.prompts[1]
    assert len(outcome.specs) == 1

    ask = _scripted("", "still nothing")
    outcome = agentic.negotiate(store, sheet, BRIEF, ask, store.config.write)
    assert outcome.specs == []
    assert outcome.rounds == 2


def test_a_long_observation_is_clipped(store):
    store.record(type="fact", fields={"subject": "long"}, abstract="Long body", body="x" * 50)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    store.config.write.tool_result_chars = 40
    ask = _scripted(_call("read", name="long"), "")
    agentic.negotiate(store, sheet, BRIEF, ask, store.config.write)
    assert "(truncated)" in ask.prompts[1]


def test_the_text_protocol_can_choose_bounded_evidence_recall(store):
    store.config.write.recall_with_evidence_enabled = True
    old = _existing(store)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    ask = _scripted(
        _call(toolkit.TOOL_RECALL_WITH_EVIDENCE, query="queue timeout"),
        _supersede(old.name),
    )

    outcome = agentic.negotiate(store, sheet, BRIEF, ask, store.config.write)

    assert old.name in outcome.sheet.handle_names()
    assert "infra/queue.yaml" in ask.prompts[1]
    assert outcome.rounds == 2


def test_distill_runs_the_negotiation_and_reports_the_rounds(store):
    old = _existing(store)
    messages = _messages(store)
    ask = _scripted(_call("recall", query="queue timeout"), _supersede(old.name))
    report = distill.distill(store, "boundary", messages, ask)
    assert report.batches[0].rounds == 2
    assert report.batches[0].written == ("queue-timeout-30s",)
    assert not store.find(old.name).is_active()


class ScriptedToolReasoner:
    """A native tool-use reasoner: it calls the toolkit, it never returns operations as text."""

    def __init__(self, *calls):
        self.calls = calls
        self.instructions = ""
        self.material = ""
        self.replies = []

    def converse(self, instructions, material, kit):
        self.instructions, self.material = instructions, material
        for name, arguments in self.calls:
            self.replies.append(kit.call(name, arguments))

    def __call__(self, prompt):
        raise AssertionError("a tool reasoner negotiates through its tools")


def _look(query):
    return (toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: query})


def _submit(*operations):
    return (toolkit.TOOL_SUBMIT, {toolkit.ARG_OPERATIONS: [json.loads(op) for op in operations]})


def test_a_tool_reasoner_gets_instructions_and_material_apart_and_its_submission_is_the_answer(
    store,
):
    old = _existing(store)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    reasoner = ScriptedToolReasoner(_look("queue timeout"), _submit(_supersede(old.name)))
    outcome = agentic.negotiate(store, sheet, BRIEF, reasoner, store.config.write)
    assert (reasoner.instructions, reasoner.material) == (BRIEF.tool_system(), BRIEF.material)
    assert outcome.errors == []
    assert outcome.specs == [json.loads(_supersede(old.name))]
    assert old.name in outcome.sheet.handle_names()
    assert outcome.rounds == len(reasoner.calls)


def test_a_tool_reasoner_may_look_as_often_as_it_likes(store):
    old = _existing(store)
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    store.config.write.max_rounds = 1
    looks = [_look(f"queue timeout {index}") for index in range(12)]
    reasoner = ScriptedToolReasoner(*looks, _look("queue timeout"), _submit(_supersede(old.name)))
    outcome = agentic.negotiate(store, sheet, BRIEF, reasoner, store.config.write)
    assert outcome.errors == []
    assert outcome.rounds == len(reasoner.calls) > store.config.write.max_rounds
    assert not any(reply.is_error for reply in reasoner.replies)


def test_a_tool_reasoner_that_submits_nothing_yields_an_error_and_no_operations(store):
    messages = _messages(store)
    sheet = _empty_sheet(store, messages)
    reasoner = ScriptedToolReasoner(_look("queue timeout"))
    outcome = agentic.negotiate(store, sheet, BRIEF, reasoner, store.config.write)
    assert outcome.specs == []
    assert outcome.errors


def test_distill_through_a_tool_reasoner_writes_and_reports_its_calls(store):
    old = _existing(store)
    messages = _messages(store)
    reasoner = ScriptedToolReasoner(_look("queue timeout"), _submit(_supersede(old.name)))
    report = distill.distill(store, "boundary", messages, reasoner)
    assert report.batches[0].written == ("queue-timeout-30s",)
    assert report.batches[0].rounds == len(reasoner.calls)
    assert not store.find(old.name).is_active()
    batch_line = "our queue timeout is 30 seconds"
    assert batch_line in reasoner.material.lower()
    assert batch_line not in reasoner.instructions.lower()
    assert reasoner.instructions.split("\n", 1)[0] not in reasoner.material
    assert toolkit.TOOL_SUBMIT in reasoner.instructions
