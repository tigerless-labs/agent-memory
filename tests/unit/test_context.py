"""The read surface that decides disclosure itself, instead of delegating it to the host."""

from agent_memory.core.context import MEMORY_HEADER, RAW_HEADER, build
from agent_memory.core.recall import Recall


def _sections(text):
    memory, separator, raw = text.partition(RAW_HEADER)
    return memory, raw if separator else ""


def test_context_is_deterministic_for_the_same_store_and_question(seeded):
    first = build(seeded, "deploy drain queue")
    second = build(seeded, "deploy drain queue")
    assert first.text == second.text
    assert first.entries == second.entries


def test_the_top_entries_arrive_as_full_text_and_the_tail_as_abstracts(seeded):
    query = "deploy drain queue file truth concise answers"
    wide = build(seeded, query)
    seeded.config.recall.context_full_text_entries = 1
    narrow = build(seeded, query)

    assert wide.entries == narrow.entries > 1
    assert len(narrow.text) < len(wide.text)
    opened = seeded.read(narrow.names[0]).text
    assert opened.strip() and opened.strip() in narrow.text


def test_an_empty_store_says_so_rather_than_pretending(store):
    context = build(store, "anything at all")
    assert context.is_empty()
    assert context.text


def test_context_carries_what_recall_carries(seeded):
    hits = Recall(seeded).recall("deploy drain queue")
    context = build(seeded, "deploy drain queue")
    assert context.entries == len(hits)
    assert hits[0].abstract in context.text


def test_reads_behind_the_context_do_not_mutate_truth(seeded):
    import hashlib

    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in seeded.layout.truth_files()}
    build(seeded, "deploy drain queue")
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in seeded.layout.truth_files()}
    assert after == before


def test_deep_context_reaches_raw_material(store):
    store.record(
        abstract="Watches nature documentaries",
        type="preference",
        domain="user",
        name="nature-documentaries",
    )
    store.archive.append_session(
        "s1", "user: the follow-up you named was 'My Octopus Teacher' and it cost 42 dollars\n"
    )
    store.sync_index()
    assert "Octopus" not in build(store, "My Octopus Teacher", deep=False).text
    assert "Octopus" in build(store, "My Octopus Teacher", deep=True).text


def test_deep_context_separates_memory_from_raw_evidence(store):
    store.record(
        abstract="Watches nature documentaries",
        body="Nature documentaries are a current preference.",
        type="preference",
        domain="user",
        name="nature-documentaries",
    )
    store.archive.append_session(
        "s1", "user: My Octopus Teacher was the follow-up and it cost 42 dollars\n"
    )
    store.sync_index()

    context = build(store, "nature documentary My Octopus Teacher 42 dollars", deep=True)
    memory, raw = _sections(context.text)

    assert context.text.startswith(MEMORY_HEADER)
    assert raw
    assert "Watches nature documentaries" in memory
    assert "My Octopus Teacher" not in memory
    assert "My Octopus Teacher" in raw


def test_raw_hits_do_not_consume_the_memory_full_text_budget(store):
    body = "The full distilled detail says nature documentaries remain the preference."
    store.record(
        abstract="Nature documentary preference",
        body=body,
        type="preference",
        domain="user",
        name="nature-documentary-preference",
        weight=store.config.weight.floor,
    )
    store.archive.append_session(
        "s1", "user: nature documentary follow-up My Octopus Teacher cost 42 dollars\n"
    )
    store.sync_index()
    store.config.recall.context_full_text_entries = 1
    store.config.recall.raw_relevance_factor = 100.0

    context = build(store, "nature documentary follow-up", deep=True)
    memory, raw = _sections(context.text)

    assert raw
    assert body in memory


def test_a_raw_only_deep_context_is_evidence_not_memory_truth(store):
    store.archive.append_session(
        "s1", "user: My Octopus Teacher was the follow-up and it cost 42 dollars\n"
    )
    store.sync_index()

    context = build(store, "My Octopus Teacher 42 dollars", deep=True)
    memory, raw = _sections(context.text)

    assert not context.is_empty()
    assert MEMORY_HEADER not in memory
    assert raw and "My Octopus Teacher" in raw
