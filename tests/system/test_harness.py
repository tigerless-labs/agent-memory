"""M7 — the replay driver, exercised against a stub host. Fixtures never hit a live service."""

import dataclasses
import json

import pytest
from agent_memory.core.recall import Recall
from agent_memory.core.store import Store
from agent_memory.harness import arms, dataset, framing, report, sampling
from agent_memory.harness.driver import Driver, IsolationBreach
from agent_memory.harness.hosts import Host, HostResult, HostSpec
from agent_memory.harness.judge import Judge
from agent_memory.harness.metrics import STATUS_FAILED, STATUS_OK, MetricsSink, RunRecord

SECRET = "the drain window must exceed the lease TTL by ninety seconds"


def _instance(question_id, question_type, answer, secret):
    return {
        "question_id": question_id,
        "question_type": question_type,
        "question": "What must the drain window exceed?",
        "answer": answer,
        "question_date": "2026/02/01 (Sun) 10:00",
        "haystack_session_ids": ["s1", "s2", "s3"],
        "haystack_dates": ["2026/01/01", "2026/01/02", "2026/01/03"],
        "haystack_sessions": [
            [{"role": "user", "content": secret}, {"role": "assistant", "content": "noted"}],
            [{"role": "user", "content": "unrelated chatter about lunch"}],
            [{"role": "user", "content": "more unrelated chatter"}],
        ],
        "answer_session_ids": ["s1"],
    }


@pytest.fixture
def suite(tmp_path):
    path = tmp_path / "suite.json"
    path.write_text(
        json.dumps(
            [
                _instance("q1", "single-session-user", "the lease TTL", SECRET),
                _instance("q2", "multi-session", "the lease TTL", SECRET),
                _instance("q3", "single-session-user", "the lease TTL", SECRET),
            ]
        ),
        encoding="utf-8",
    )
    return path


class StubHost(Host):
    """Answers from the store when it has one, and writes what it is shown."""

    def __init__(self, fail_on: str = "", record_prompts: list | None = None):
        super().__init__(HostSpec(name="stub", binary="stub", attempts=1))
        self.fail_on = fail_on
        self.prompts = record_prompts if record_prompts is not None else []

    def run(self, prompt, store_root=None, tools_enabled=False, system_prompt="",
            max_turns=8, workdir=None):
        self.prompts.append(prompt)
        if self.fail_on and self.fail_on in prompt:
            return HostResult("", False, 0.1, "stub failure")
        if "Question:" in prompt:
            return HostResult(self._answer(store_root), True, 0.2)
        if store_root and SECRET in prompt:
            store = Store(store_root, agent="stub")
            store.record(
                abstract="The drain window must exceed the lease TTL by ninety seconds",
                type="fact",
                domain="project",
                name="drain-window-rule",
            )
        return HostResult("recorded", True, 0.3)

    def _answer(self, store_root):
        if store_root is None:
            return "I do not have that information."
        hits = Recall(Store(store_root)).recall("drain window lease")
        return hits[0].abstract if hits else "I do not have that information."


class StubJudge(Judge):
    def __init__(self):
        super().__init__(StubHost())

    def grade(self, question, expected, candidate):
        from agent_memory.harness.judge import Verdict

        return Verdict(correct="lease TTL" in candidate, seconds=0.05, ok=True, raw="stub")


def _driver(tmp_path, host, episodes):
    return Driver(
        host=host,
        judge=StubJudge(),
        workspace=tmp_path / "stores",
        sessions_per_call=2,
        run_id="test-run",
        episode_fingerprint=sampling.fingerprint(episodes),
    )


def test_the_exam_prompt_never_carries_experience_content(suite):
    episode = dataset.load(suite)[0]
    prompt = framing.exam(episode, with_memory=True)
    assert SECRET not in prompt
    assert episode.question in prompt


def test_a_one_word_turn_does_not_trip_the_isolation_gate(tmp_path, suite):
    episodes = dataset.load(suite)
    episode = episodes[0]
    noisy = dataclasses.replace(
        episode,
        sessions=(
            dataclasses.replace(
                episode.sessions[0],
                turns=(dataset.Turn(role="user", content="?"),) + episode.sessions[0].turns,
            ),
        )
        + episode.sessions[1:],
    )
    assert _driver(tmp_path, StubHost(), episodes).run(noisy, arms.W1).status == STATUS_OK


def test_the_exam_receives_the_memory_index_when_the_arm_has_memory(tmp_path, suite):
    episodes = dataset.load(suite)
    host = StubHost()
    driver = _driver(tmp_path, host, episodes)
    driver.run(episodes[0], arms.W1)
    exam_prompt = next(prompt for prompt in host.prompts if "Question:" in prompt)
    assert "drain-window-rule" in exam_prompt


def test_the_control_arm_receives_no_index(tmp_path, suite):
    episodes = dataset.load(suite)
    host = StubHost()
    _driver(tmp_path, host, episodes).run(episodes[0], arms.W0)
    exam_prompt = next(prompt for prompt in host.prompts if "Question:" in prompt)
    assert "memory store currently holds" not in exam_prompt


def test_injection_is_disabled_by_config_rather_than_by_code(tmp_path, suite):
    from agent_memory.core.config import Config
    from agent_memory.core.injection import payload

    episodes = dataset.load(suite)
    _driver(tmp_path, StubHost(), episodes).run(episodes[0], arms.W1)
    store = Store(tmp_path / "stores" / arms.W1.name / episodes[0].id)
    assert payload(store)

    store.config.recall.injection_enabled = False
    assert payload(store) == ""
    assert Config.default().recall.injection_enabled


def test_the_driver_refuses_to_score_a_run_whose_isolation_broke(tmp_path, suite, monkeypatch):
    episodes = dataset.load(suite)
    monkeypatch.setattr(framing, "exam", lambda episode, with_memory: SECRET + episode.question)
    with pytest.raises(IsolationBreach):
        _driver(tmp_path, StubHost(), episodes).run(episodes[0], arms.W1)


def test_each_run_gets_its_own_clean_working_directory(tmp_path, suite):
    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(), episodes)
    driver.run(episodes[0], arms.W1)
    workdir = tmp_path / "stores" / arms.W1.name / episodes[0].id / "cwd"
    assert workdir.is_dir()
    assert list(workdir.iterdir()) == []


def test_a_write_arm_beats_the_no_memory_control_on_the_same_episode(tmp_path, suite):
    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(), episodes)
    control = driver.run(episodes[0], arms.W0)
    written = driver.run(episodes[0], arms.W1)

    assert control.memories_written == 0
    assert not control.correct
    assert written.memories_written > 0
    assert written.correct


def test_only_blocking_arms_report_blocking_time(tmp_path, suite):
    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(), episodes)
    blocking = driver.run(episodes[0], arms.W1)
    forked = driver.run(episodes[0], arms.W2)

    assert blocking.blocking_seconds > 0
    assert forked.blocking_seconds == 0
    assert forked.experience_seconds > 0


def test_the_cold_arm_archives_the_transcript_before_distilling(tmp_path, suite):
    episodes = dataset.load(suite)
    record = _driver(tmp_path, StubHost(), episodes).run(episodes[0], arms.W3)
    store = Store(tmp_path / "stores" / arms.W3.name / episodes[0].id)
    archived = list(store.layout.sessions.glob("*.txt"))
    assert archived
    assert any(SECRET in path.read_text(encoding="utf-8") for path in archived)
    assert record.memories_written > 0


def test_a_host_failure_marks_the_run_and_never_counts_as_correct(tmp_path, suite):
    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(fail_on="Question:"), episodes)
    record = driver.run(episodes[0], arms.W1)
    assert record.status == STATUS_FAILED
    assert not record.correct
    assert record.error


def test_every_run_carries_the_fingerprints_that_license_attribution(tmp_path, suite):
    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(), episodes)
    records = [driver.run(episodes[0], arm) for arm in (arms.W0, arms.W1)]
    assert len({record.recall_fingerprint for record in records}) == 1
    assert len({record.episode_fingerprint for record in records}) == 1


def test_the_report_refuses_attribution_when_recall_drifted(tmp_path, suite):
    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(), episodes)
    sink = MetricsSink(tmp_path / "metrics")
    for arm in (arms.W0, arms.W1):
        sink.append(driver.run(episodes[0], arm))

    honest = report.summarise(sink.records())
    assert honest.attribution_is_licensed()

    drifted = sink.records()
    drifted[-1]["recall_fingerprint"] = "something-else"
    assert not report.summarise(drifted).attribution_is_licensed()


def test_sampling_is_stratified_and_reproducible(suite):
    episodes = dataset.load(suite)
    first = sampling.stratified(episodes, per_stratum=1, seed=7)
    second = sampling.stratified(episodes, per_stratum=1, seed=7)
    assert [episode.id for episode in first] == [episode.id for episode in second]
    assert len({episode.question_type for episode in first}) == len(
        {episode.question_type for episode in episodes}
    )
    assert sampling.fingerprint(first) == sampling.fingerprint(second)


def test_trimming_keeps_the_evidence_sessions_first(tmp_path, suite):
    target = tmp_path / "trimmed.json"
    dataset.trim(suite, target, sessions_per_episode=1)
    episode = dataset.load(target)[0]
    assert len(episode.sessions) == 1
    assert episode.sessions[0].id in episode.evidence_session_ids


def test_regrading_rewrites_verdicts_without_touching_the_stores(tmp_path, suite):
    from agent_memory.harness.judge import Verdict, regrade

    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(), episodes)
    sink = MetricsSink(tmp_path / "ws")
    sink.append(driver.run(episodes[0], arms.W1))
    before = sink.records()
    assert before[0]["correct"]

    class Harsh(StubJudge):
        def grade(self, question, expected, candidate):
            return Verdict(correct=False, seconds=0.0, ok=True, raw="harsh")

    stores_before = sorted(path.name for path in (tmp_path / "stores").rglob("*.md"))
    after = regrade(before, Harsh(), {episodes[0].id: episodes[0].question}, workers=1)
    sink.replace(after)

    assert not after[0]["correct"]
    assert after[0]["answer"] == before[0]["answer"]
    assert MetricsSink(tmp_path / "ws").records() == after
    assert sorted(path.name for path in (tmp_path / "stores").rglob("*.md")) == stores_before


def test_a_failed_run_is_never_regraded_into_a_correct_one(tmp_path, suite):
    from agent_memory.harness.judge import Verdict, regrade

    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(fail_on="Question:"), episodes)
    failed = [driver.run(episodes[0], arms.W1).as_dict()]

    class Generous(StubJudge):
        def grade(self, question, expected, candidate):
            return Verdict(correct=True, seconds=0.0, ok=True, raw="generous")

    assert not regrade(failed, Generous(), {}, workers=1)[0]["correct"]


def test_an_arm_can_be_expressed_as_a_config_override(tmp_path):
    from agent_memory.harness.main import _configured

    config = _configured(["recall.raw_enabled=false", "recall.default_limit=5"])
    assert config.recall.raw_enabled is False
    assert config.recall.default_limit == 5
    assert config.recall_fingerprint() != _configured([]).recall_fingerprint()

    with pytest.raises(ValueError):
        _configured(["recall.not_a_knob=1"])


def test_metrics_records_round_trip_through_the_sink(tmp_path):
    sink = MetricsSink(tmp_path)
    record = RunRecord(
        run_id="r", arm="W1", host="stub", episode_id="q1", question_type="t",
        status=STATUS_OK, correct=True, answer="a", expected="a", memories_written=1,
        experience_calls=1, experience_seconds=1.0, blocking_seconds=1.0, exam_seconds=1.0,
        judge_seconds=1.0, recall_fingerprint="f", episode_fingerprint="e",
    )
    sink.append(record)
    assert sink.records()[0]["episode_id"] == "q1"
    assert set(sink.records()[0]) == set(record.as_dict())
