import dataclasses

from agent_memory.core import memory_md


def test_one_oversized_entry_does_not_hide_every_remaining_memory(store):
    first = store.record(abstract="A" * 180, type="fact", body="long", name="long")
    second = store.record(abstract="short fact", type="fact", body="short", name="short")
    first.weight, second.weight = 5.0, 1.0
    config = dataclasses.replace(
        store.config, memory_md=dataclasses.replace(store.config.memory_md, budget_bytes=100)
    )
    rendered = memory_md.render([first, second], config, str(store.root))
    assert "[short]" in rendered
    assert "[long]" not in rendered
    assert len(rendered.encode("utf-8")) <= config.memory_md.budget_bytes


def test_root_index_header_cannot_exceed_its_byte_budget(store):
    from agent_memory.core import memory_md

    for budget in (0, 5, 13):
        store.config.memory_md.budget_bytes = budget
        rendered = memory_md.render([], store.config)
        assert len(rendered.encode("utf-8")) <= budget
