import pytest
from agent_memory.harness import arms
from agent_memory.harness.dataset import Episode
from agent_memory.harness.driver import Driver, ExperiencePhase
from agent_memory.harness.systems import NativeSystem


class Host:
    name = "synthetic"

    def run(self, *args, **kwargs):
        raise RuntimeError("synthetic host failure")


def test_replay_releases_resources_after_host_exception(tmp_path, monkeypatch):
    system = NativeSystem()
    released = []
    monkeypatch.setattr(system, "release", released.append)
    driver = Driver(
        Host(),
        object(),
        tmp_path / "stores",
        1,
        "fixture",
        "fingerprint",
        system=system,
        ask=lambda prompt: "",
    )
    monkeypatch.setattr(driver, "_experience", lambda *args: ExperiencePhase(0, 0.0, 0.0, 0))
    episode = Episode("q1", "Question", "Answer", "single", "2026-01-01", (), ())
    with pytest.raises(RuntimeError, match="synthetic"):
        driver.run(episode, arms.W1)
    assert released == [tmp_path / "stores" / "W1" / "q1"]
