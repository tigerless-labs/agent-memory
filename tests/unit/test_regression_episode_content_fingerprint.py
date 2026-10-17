import dataclasses

from agent_memory.harness.dataset import Episode, Session, Turn
from agent_memory.harness.sampling import fingerprint


def test_unchanged_ids_cannot_hide_changed_benchmark_inputs():
    episode = Episode(
        "q1",
        "Question",
        "Answer",
        "single",
        "2026-01-01",
        (Session("s1", "2026-01-01", (Turn("user", "Evidence"),)),),
        ("s1",),
    )
    original = fingerprint([episode])
    changes = [
        dataclasses.replace(episode, question="Changed question"),
        dataclasses.replace(episode, answer="Changed answer"),
        dataclasses.replace(
            episode,
            sessions=(
                dataclasses.replace(episode.sessions[0], turns=(Turn("user", "Changed evidence"),)),
            ),
        ),
    ]
    assert all(fingerprint([changed]) != original for changed in changes)
    assert fingerprint([episode]) == original
