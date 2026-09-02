"""Sleeping a store tree is an experiment step: it must copy, not consume, the control."""

import json

from agent_memory.core.store import Store
from agent_memory.harness.main import main as exp_main


def _seed(root, name):
    store = Store(root, agent="seed")
    store.init()
    store.record(
        abstract=f"Queue drain timeout is 30 seconds as of {name}",
        type="fact",
        domain="project",
        name="drain-timeout",
    )
    return store


def test_sleeping_copies_the_tree_and_leaves_the_control_untouched(tmp_path, capsys):
    source = tmp_path / "stores" / "W2"
    for episode in ("q1", "q2"):
        _seed(source / episode, episode)
    before = {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*.md")
        if "dream-reports" not in str(path)
    }

    target = tmp_path / "slept" / "W2"
    assert exp_main(["sleep-stores", "--stores", str(source), "--target", str(target)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["stores"] == 2
    after = {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*.md")
        if "dream-reports" not in str(path)
    }
    assert after == before
    assert (target / "q1" / "MEMORY.md").exists()
    assert list((target / "q1" / "dream-reports").glob("*.md"))


def test_sleeping_an_existing_target_refuses_rather_than_mixing_arms(tmp_path):
    import pytest

    source = tmp_path / "stores" / "W2"
    _seed(source / "q1", "q1")
    target = tmp_path / "slept"
    target.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        exp_main(["sleep-stores", "--stores", str(source), "--target", str(target)])


def test_advancing_the_clock_is_what_lets_forgetting_happen_at_all(tmp_path, capsys):
    from agent_memory.core.record import STATUS_STALE

    source = tmp_path / "stores" / "W2"
    store = _seed(source / "q1", "q1")
    threshold = store.config.manage.stale_after_days

    same_day = tmp_path / "same-day" / "W2"
    assert exp_main(["sleep-stores", "--stores", str(source), "--target", str(same_day)]) == 0
    capsys.readouterr()
    assert not [r for r in Store(same_day / "q1").records() if r.status == STATUS_STALE]

    much_later = tmp_path / "later" / "W2"
    assert exp_main([
        "sleep-stores", "--stores", str(source), "--target", str(much_later),
        "--days-later", str(threshold + 1),
    ]) == 0
    capsys.readouterr()
    assert [r for r in Store(much_later / "q1").records() if r.status == STATUS_STALE]
