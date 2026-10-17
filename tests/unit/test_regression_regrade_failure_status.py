from agent_memory.harness.judge import Verdict, regrade


def test_regrade_failure_does_not_become_valid_incorrect_score():
    class BrokenJudge:
        def grade(self, *args):
            return Verdict(False, 0.0, False, "", "synthetic judge failure")

    record = {
        "status": "ok",
        "episode_id": "q1",
        "expected": "Answer",
        "answer": "Candidate",
        "correct": True,
    }
    updated = regrade([record], BrokenJudge(), {"q1": "Question"}, 1)[0]
    assert updated["status"] == "failed"
    assert updated["error"] == "synthetic judge failure"
