from agent_memory.executor.hosts import HostResult
from agent_memory.harness import arms
from agent_memory.harness.dataset import Episode
from agent_memory.harness.driver import Driver, ExperiencePhase
from agent_memory.harness.judge import Verdict


class Host:
    name = "synthetic"

    def run(self, *args, **kwargs):
        return HostResult("Answer", True, 0.0)


class Judge:
    def grade(self, *args):
        return Verdict(True, 0.0, True, "yes")


def test_experience_failure_cannot_be_graded_as_success(tmp_path, monkeypatch):
    driver = Driver(
        Host(), Judge(), tmp_path / "stores", 1, "fixture", "fingerprint", ask=lambda prompt: ""
    )
    monkeypatch.setattr(driver, "_experience", lambda *args: ExperiencePhase(1, 0.0, 0.0, 1))
    episode = Episode("q1", "Question", "Answer", "single", "2026-01-01", (), ())
    record = driver.run(episode, arms.W1)
    assert record.status == "failed"
    assert not record.correct
    assert "experience" in record.error.lower()
