"""Sleeping a store tree is an experiment step: it must copy, not consume, the control."""

import json
import re

from agent_memory.core.store import Store
from agent_memory.harness.main import main as exp_main


def _seed(root, name):
    store = Store(root, agent="seed")
    store.init()
    store.record(
        abstract=f"Queue drain timeout is 30 seconds as of {name}",
        type="fact",
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
    source = tmp_path / "stores" / "W2"
    store = _seed(source / "q1", "q1")
    threshold = store.config.weight.decay_after_days
    initial = store.config.weight.initial

    same_day = tmp_path / "same-day" / "W2"
    assert exp_main(["sleep-stores", "--stores", str(source), "--target", str(same_day)]) == 0
    capsys.readouterr()
    assert all(r.weight >= initial for r in Store(same_day / "q1").records())

    much_later = tmp_path / "later" / "W2"
    assert (
        exp_main(
            [
                "sleep-stores",
                "--stores",
                str(source),
                "--target",
                str(much_later),
                "--days-later",
                str(threshold + 1),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert all(r.weight < initial for r in Store(much_later / "q1").records())


def _twins(root):
    store = Store(root, agent="seed")
    store.init()
    store.record(
        abstract="The drain window closes before the worker lease expires",
        type="experience",
        body="Short.",
        name="drain-window-first",
    )
    store.record(
        abstract="The drain window closes before the worker lease expires again",
        type="experience",
        body="Longer body carrying the lease TTL and the fix that worked.",
        name="drain-window-second",
    )
    return store


def test_a_sleep_without_a_reasoner_decides_nothing(tmp_path, capsys):
    _twins(tmp_path / "stores" / "W2" / "q1")
    target = tmp_path / "slept" / "W2"
    assert (
        exp_main(
            ["sleep-stores", "--stores", str(tmp_path / "stores" / "W2"), "--target", str(target)]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["decisions"] == 0


def test_a_reasoned_sleep_records_what_it_decided(tmp_path, capsys, monkeypatch):
    _twins(tmp_path / "stores" / "W2" / "q1")
    monkeypatch.setattr(
        "agent_memory.executor.reasoners.HostReasoner.__call__",
        lambda self, prompt: "\n".join(
            json.dumps({"proposal": found, "verdict": "reject"})
            for found in re.findall(r"^- ([0-9a-f]{12}) \(", prompt, flags=re.MULTILINE)
        ),
    )
    target = tmp_path / "slept" / "W2"
    assert (
        exp_main(
            [
                "sleep-stores",
                "--stores",
                str(tmp_path / "stores" / "W2"),
                "--target",
                str(target),
                "--reason",
                "host",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["decisions"] > 0
    assert payload["proposals"] == 0


def test_the_per_sleep_cap_is_a_knob_the_step_can_lower(tmp_path, capsys, monkeypatch):
    _twins(tmp_path / "stores" / "W2" / "q1")
    monkeypatch.setattr(
        "agent_memory.executor.reasoners.HostReasoner.__call__",
        lambda self, prompt: "\n".join(
            json.dumps({"proposal": found, "verdict": "accept"})
            for found in re.findall(r"^- ([0-9a-f]{12}) \(", prompt, flags=re.MULTILINE)
        ),
    )
    target = tmp_path / "slept" / "W2"
    assert (
        exp_main(
            [
                "sleep-stores",
                "--stores",
                str(tmp_path / "stores" / "W2"),
                "--target",
                str(target),
                "--reason",
                "host",
                "--set",
                "manage.max_supersedes_per_sleep=0",
            ]
        )
        == 0
    )
    slept = Store(target / "q1", agent="check")
    assert slept.find("drain-window-first").is_active()
    assert json.loads(capsys.readouterr().out)["decisions"] == 0
