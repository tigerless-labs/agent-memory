import pytest
from agent_memory.harness.report import summarise


def row(arm, episode):
    return {
        "arm": arm,
        "episode_id": episode,
        "status": "ok",
        "correct": True,
        "question_type": "single",
        "blocking_seconds": 0,
        "experience_seconds": 0,
        "exam_seconds": 0,
        "memories_written": 0,
        "recall_fingerprint": "same",
        "episode_fingerprint": "same",
    }


def test_matching_global_fingerprints_do_not_license_unpaired_arms():
    assert not summarise([row("W1", "q1"), row("W2", "q2")]).attribution_is_licensed()
    assert summarise([row("W1", "q1"), row("W2", "q1")]).attribution_is_licensed()


def test_duplicate_results_do_not_license_attribution():
    assert not summarise(
        [row("W1", "q1"), row("W1", "q1"), row("W2", "q1")]
    ).attribution_is_licensed()


@pytest.mark.parametrize("identity", [None, "", " \t", 0, [], {}])
def test_missing_episode_identity_cannot_license_attribution(identity):
    records = [row("W1", identity), row("W2", identity)]
    assert not summarise(records).attribution_is_licensed()
