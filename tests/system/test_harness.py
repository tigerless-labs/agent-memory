"""M7 — the replay driver, exercised against a stub host. Fixtures never hit a live service."""

import dataclasses
import json
import os
import subprocess

import pytest
from agent_memory.core.config import Config
from agent_memory.core.recall import Recall
from agent_memory.core.store import Store
from agent_memory.executor.hosts import Host, HostResult, HostSpec
from agent_memory.harness import arms, dataset, framing, report, sampling, systems
from agent_memory.harness.driver import Driver, IsolationBreach
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
            max_turns=8, workdir=None, **_):
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
    prompt = framing.exam(episode, systems.build(systems.NATIVE, Config.default()).exam_preamble())
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
    monkeypatch.setattr(framing, "exam", lambda episode, preamble: SECRET + episode.question)
    with pytest.raises(IsolationBreach):
        _driver(tmp_path, StubHost(), episodes).run(episodes[0], arms.W1)


def test_each_run_gets_its_own_clean_working_directory(tmp_path, suite):
    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(), episodes)
    driver.run(episodes[0], arms.W1)
    workdir = tmp_path / "cwd" / arms.W1.name / episodes[0].id
    assert workdir.is_dir()
    assert list(workdir.iterdir()) == []


def test_the_host_never_stands_inside_the_store_it_is_measured_on(tmp_path, suite):
    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(), episodes)
    driver.run(episodes[0], arms.W1)
    store_root = tmp_path / "stores" / arms.W1.name / episodes[0].id
    workdir = tmp_path / "cwd" / arms.W1.name / episodes[0].id
    assert store_root not in workdir.parents
    assert not (store_root / "cwd").exists()


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


def test_reusing_stores_skips_the_experience_phase_and_keeps_the_written_memories(tmp_path, suite):
    episodes = dataset.load(suite)
    host = StubHost()
    _driver(tmp_path, host, episodes).run(episodes[0], arms.W1)
    written = sorted(
        path.name for path in (tmp_path / "stores" / arms.W1.name / episodes[0].id).rglob("*.md")
    )

    replay_host = StubHost()
    replay = Driver(
        host=replay_host,
        judge=StubJudge(),
        workspace=tmp_path / "replay",
        sessions_per_call=2,
        run_id="replay",
        episode_fingerprint=sampling.fingerprint(episodes),
        reuse_stores=tmp_path / "stores",
    )
    record = replay.run(episodes[0], arms.W1)

    assert record.experience_calls == 0
    assert len(replay_host.prompts) == 1
    assert record.correct
    assert sorted(
        path.name for path in (tmp_path / "stores" / arms.W1.name / episodes[0].id).rglob("*.md")
    ) == written


def test_reusing_a_store_that_was_never_written_is_an_error(tmp_path, suite):
    episodes = dataset.load(suite)
    replay = Driver(
        host=StubHost(),
        judge=StubJudge(),
        workspace=tmp_path / "replay",
        sessions_per_call=2,
        run_id="replay",
        episode_fingerprint=sampling.fingerprint(episodes),
        reuse_stores=tmp_path / "nothing-here",
    )
    with pytest.raises(FileNotFoundError):
        replay.run(episodes[0], arms.W1)


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


def test_a_write_path_inside_a_worktree_is_refused(tmp_path):
    from agent_memory.harness.workspace import DisposableWorkspace, for_writing

    inside = tmp_path / ".claude" / "worktrees" / "feat-x" / "experiments" / "runs" / "p1"
    with pytest.raises(DisposableWorkspace) as refusal:
        for_writing(inside)
    assert "worktree" in str(refusal.value)


def test_a_write_path_in_the_main_tree_is_accepted_and_absolute(tmp_path):
    from agent_memory.harness.workspace import for_writing

    resolved = for_writing(tmp_path / "experiments" / "runs" / "p1")

    assert resolved.is_absolute()
    assert resolved == (tmp_path / "experiments" / "runs" / "p1").resolve()


def test_a_directory_merely_named_worktrees_is_not_a_worktree(tmp_path):
    from agent_memory.harness.workspace import for_writing

    assert for_writing(tmp_path / "worktrees" / "runs")


def test_every_writing_subcommand_guards_its_path():
    import inspect

    from agent_memory.harness import main as main_module

    source = inspect.getsource(main_module)
    for handler in ("_run", "_regrade", "_interop", "_sleep_stores", "_prepare"):
        body = source.split(f"def {handler}(")[1].split("\ndef ")[0]
        assert "for_writing(" in body, f"{handler} writes without guarding its path"


def test_the_cli_refuses_a_worktree_target_without_a_traceback(tmp_path, capsys):
    from agent_memory.harness.main import main

    code = main(
        [
            "sleep-stores",
            "--stores", str(tmp_path / "src"),
            "--target", str(tmp_path / ".claude" / "worktrees" / "b" / "stores"),
        ]
    )

    assert code == 1
    assert "worktree" in capsys.readouterr().err


def _record(**overrides):
    fields = dict(
        run_id="r", arm="W2", host="stub", episode_id="q1", question_type="t",
        status=STATUS_OK, correct=True, answer="a", expected="a", memories_written=1,
        experience_calls=1, experience_seconds=1.0, blocking_seconds=1.0, exam_seconds=1.0,
        judge_seconds=1.0, recall_fingerprint="f", episode_fingerprint="e",
    )
    fields.update(overrides)
    return RunRecord(**fields)


def test_two_sleeps_of_the_same_arm_are_two_rows_in_the_report(tmp_path):
    sink = MetricsSink(tmp_path)
    sink.append(_record(episode_id="q1", manage="off", correct=True))
    sink.append(_record(episode_id="q1", manage="reasoned", correct=False))
    summary = report.summarise(sink.records())
    assert {arm.arm for arm in summary.arms} == {"W2+off", "W2+reasoned"}
    assert summary.attribution_is_licensed()


def test_a_run_that_never_slept_still_summarises_under_its_arm_alone(tmp_path):
    sink = MetricsSink(tmp_path)
    sink.append(_record())
    assert [arm.arm for arm in report.summarise(sink.records()).arms] == ["W2"]


def test_records_written_before_the_manage_dimension_existed_still_summarise(tmp_path):
    sink = MetricsSink(tmp_path)
    sink.append(_record())
    older = sink.records()
    older[0].pop("manage")
    assert [arm.arm for arm in report.summarise(older).arms] == ["W2"]


class MemcoreStubHost(StubHost):
    """Reaches MemCore only through the environment the system hands it, like a real host."""

    def run(self, prompt, store_root=None, tools_enabled=False, system_prompt="",
            max_turns=8, workdir=None, environment=None, **_):
        self.prompts.append(prompt)
        env = dict(os.environ) | (environment or {})
        if "Question:" in prompt:
            listed = subprocess.run(
                ["memcore", "recall", "plant"], env=env, capture_output=True, text=True,
                check=False,
            ).stdout.split()
            if not listed:
                return HostResult("I do not have that information.", True, 0.2)
            body = subprocess.run(
                ["memcore", "get", " ".join(listed)], env=env, capture_output=True,
                text=True, check=False,
            ).stdout
            return HostResult(body.strip().splitlines()[-1], True, 0.2)
        if SECRET in prompt:
            subprocess.run(
                ["memcore", "create", "drain window rule"], env=env, check=True,
                input="---\nabstract: drain window rule\n---\nthe lease TTL\n", text=True,
            )
        return HostResult("recorded", True, 0.3)


def _memcore_driver(tmp_path, host, episodes, memcore_home):
    return Driver(
        host=host,
        judge=StubJudge(),
        workspace=tmp_path / "stores",
        sessions_per_call=2,
        run_id="test-run",
        episode_fingerprint=sampling.fingerprint(episodes),
        system=systems.build(systems.MEMCORE, Config.default(), memcore_home=memcore_home),
    )


def test_the_driver_runs_an_episode_through_memcore_end_to_end(tmp_path, suite, memcore_home):
    episodes = dataset.load(suite)
    host = MemcoreStubHost()
    record = _memcore_driver(tmp_path, host, episodes, memcore_home).run(episodes[0], arms.W2)

    assert record.system == systems.MEMCORE
    assert record.correct
    assert record.memories_written == 1
    assert record.recall_fingerprint != Config.default().recall_fingerprint()

    root = tmp_path / "stores" / arms.W2.name / episodes[0].id
    calls = (root / "calls.log").read_text(encoding="utf-8").split("\n")
    assert calls.count("stop") == 2
    assert calls.index("stop") < calls.index("recall")
    assert not (root / "archive").exists()
    exam_prompt = next(prompt for prompt in host.prompts if "Question:" in prompt)
    assert "drain window rule" in exam_prompt
    assert "memcore" in exam_prompt


def test_the_native_system_is_the_default(tmp_path, suite):
    episodes = dataset.load(suite)
    record = _driver(tmp_path, StubHost(), episodes).run(episodes[0], arms.W1)
    assert record.system == systems.NATIVE


def test_the_fixed_exam_refuses_a_system_it_cannot_build_context_for(tmp_path, suite, memcore_home):
    from agent_memory.harness import exam as exam_module

    episodes = dataset.load(suite)
    with pytest.raises(ValueError, match="fixed"):
        Driver(
            host=MemcoreStubHost(),
            judge=StubJudge(),
            workspace=tmp_path / "stores",
            sessions_per_call=2,
            run_id="t",
            episode_fingerprint=sampling.fingerprint(episodes),
            system=systems.build(systems.MEMCORE, Config.default(), memcore_home=memcore_home),
            exam_mode=exam_module.MODE_FIXED,
        )


def test_the_report_groups_by_system_and_refuses_attribution_across_them(
    tmp_path, suite, memcore_home
):
    episodes = dataset.load(suite)
    sink = MetricsSink(tmp_path / "metrics")
    sink.append(_driver(tmp_path, StubHost(), episodes).run(episodes[0], arms.W2))
    sink.append(
        _memcore_driver(tmp_path / "mc", MemcoreStubHost(), episodes, memcore_home).run(
            episodes[0], arms.W2
        )
    )

    summary = report.summarise(sink.records())
    assert [(row.system, row.arm) for row in summary.arms] == [
        (systems.NATIVE, "W2"), (systems.MEMCORE, "W2"),
    ]
    assert not summary.attribution_is_licensed()
    rendered = report.render(summary)
    assert systems.MEMCORE in rendered and systems.NATIVE in rendered


def test_old_records_without_a_system_field_still_report(tmp_path, suite):
    episodes = dataset.load(suite)
    sink = MetricsSink(tmp_path / "metrics")
    sink.append(_driver(tmp_path, StubHost(), episodes).run(episodes[0], arms.W1))
    records = sink.records()
    del records[0]["system"]
    assert report.summarise(records).arms[0].system == systems.NATIVE


class LimitedHost(StubHost):
    """Fails the way a host does when the account's quota is exhausted."""

    def run(self, prompt, store_root=None, tools_enabled=False, system_prompt="", max_turns=8,
            workdir=None, **_):
        self.prompts.append(prompt)
        return HostResult("", False, 0.1, "You've hit your session limit · resets 9:10pm")


def test_a_quota_failure_halts_the_matrix_instead_of_failing_every_episode(tmp_path, suite):
    from agent_memory.harness.main import _execute

    episodes = dataset.load(suite)
    driver = _driver(tmp_path, LimitedHost(), episodes)
    sink = MetricsSink(tmp_path / "ws")
    jobs = [(episode, arms.W1) for episode in episodes]

    halted = _execute(driver, jobs, sink, concurrency=1)

    assert "limit" in halted
    assert 0 < len(sink.records()) < len(jobs)


def test_an_ordinary_failure_does_not_halt_the_matrix(tmp_path, suite):
    from agent_memory.harness.main import _execute

    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(fail_on="Question:"), episodes)
    sink = MetricsSink(tmp_path / "ws")
    jobs = [(episode, arms.W1) for episode in episodes]

    assert _execute(driver, jobs, sink, concurrency=2) == ""
    assert len(sink.records()) == len(jobs)


def test_resume_reruns_only_what_did_not_succeed(tmp_path, suite):
    from agent_memory.harness.main import _resumable

    episodes = dataset.load(suite)
    driver = _driver(tmp_path, StubHost(), episodes)
    sink = MetricsSink(tmp_path / "ws")
    fingerprint = sampling.fingerprint(episodes)
    sink.append(driver.run(episodes[0], arms.W1))
    failing = _driver(tmp_path, StubHost(fail_on="Question:"), episodes)
    sink.append(failing.run(episodes[1], arms.W1))
    jobs = [(episode, arms.W1) for episode in episodes]

    remaining = _resumable(sink, jobs, fingerprint, systems.NATIVE)

    assert [episode.id for episode, _ in remaining] == [episodes[1].id, episodes[2].id]
    assert [record["episode_id"] for record in sink.records()] == [episodes[0].id]


def test_resume_refuses_a_workspace_from_another_episode_set_or_system(tmp_path, suite):
    from agent_memory.harness.main import _resumable

    episodes = dataset.load(suite)
    sink = MetricsSink(tmp_path / "ws")
    sink.append(_driver(tmp_path, StubHost(), episodes).run(episodes[0], arms.W1))
    jobs = [(episode, arms.W1) for episode in episodes]

    with pytest.raises(ValueError, match="episode"):
        _resumable(sink, jobs, "another-fingerprint", systems.NATIVE)
    with pytest.raises(ValueError, match="system"):
        _resumable(sink, jobs, sampling.fingerprint(episodes), systems.MEMCORE)
