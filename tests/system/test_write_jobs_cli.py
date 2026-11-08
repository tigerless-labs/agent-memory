"""The Write job queue end to end: hook spawn, CLI job and drain runs, jobs surface, doctor."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import pathlib
import subprocess
import sys
import time

import pytest
from agent_memory.adapters import capture, hook_entry
from agent_memory.cli.main import EXIT_ERROR, EXIT_INVALID, EXIT_OK, main
from agent_memory.core import toolkit, write_jobs, write_run
from agent_memory.core.config import Config
from agent_memory.core.store import Store
from agent_memory.core.watermark import Watermark
from agent_memory.core.write_jobs import (
    STATE_CANCELLED,
    STATE_DEAD,
    STATE_QUEUED,
    STATE_RUNNING,
    STATE_SUCCEEDED,
    WriteJobs,
)


def _capture(store, session: str = "boundary", count: int = 2) -> None:
    capture.capture(
        store,
        session,
        [f"user: the {session} queue timeout is {30 + number} seconds" for number in range(count)],
        source="pause",
    )


def _operation() -> dict[str, object]:
    return {
        "type": "fact",
        "op": "new",
        "fields": {"project": "queue", "subject": "timeout"},
        "abstract": "The queue timeout is 30 seconds",
        "provenance": ["0"],
    }


@pytest.fixture
def cli(store, capsys):
    def run(*argv, expect=EXIT_OK):
        code = main(["--store", str(store.root), "--json", *argv])
        captured = capsys.readouterr()
        assert code == expect, captured.err or captured.out
        stream = captured.out if captured.out.strip() else captured.err
        return json.loads(stream) if stream.strip() else {}

    run.root = store.root
    return run


def test_a_boundary_hook_enqueues_the_job_and_spawns_its_worker(store, monkeypatch):
    launched = {}

    def popen(command, **kwargs):
        launched.update(command=command, kwargs=kwargs)

    monkeypatch.setattr(hook_entry.subprocess, "Popen", popen)
    response = hook_entry.handle(
        store,
        {
            "host": "codex",
            "hook_event_name": "Stop",
            "session_id": "boundary",
            "items": ["user: one"],
        },
    )

    assert response[hook_entry.KEY_DISTILL] == hook_entry.DISTILL_LAUNCHED
    job_id = launched["command"][launched["command"].index(hook_entry.JOB_FLAG) + 1]
    job = WriteJobs(store).get(job_id)
    assert job.state == STATE_QUEUED
    assert job.session == "boundary"
    assert job.target == 1
    assert launched["command"][-5:] == [
        hook_entry.JOB_FLAG,
        job.id,
        hook_entry.SOURCE_HOST_FLAG,
        "codex",
        hook_entry.AUTO_DREAM_FLAG,
    ]


def test_a_failed_spawn_leaves_the_job_queued(store, monkeypatch):
    def refusing(*args, **kwargs):
        raise OSError("no executor binary")

    monkeypatch.setattr(hook_entry.subprocess, "Popen", refusing)
    response = hook_entry.handle(
        store,
        {
            "host": "codex",
            "hook_event_name": "Stop",
            "session_id": "boundary",
            "items": ["user: one"],
        },
    )

    assert response[hook_entry.KEY_DISTILL] == hook_entry.DISTILL_SKIPPED
    queued = WriteJobs(store).list((STATE_QUEUED,))
    assert [job.session for job in queued] == ["boundary"]


def test_session_start_drains_due_jobs_through_one_detached_worker(store, monkeypatch):
    _capture(store)
    WriteJobs(store).enqueue("boundary", "codex")
    launched = {}

    def popen(command, **kwargs):
        launched.update(command=command, kwargs=kwargs)

    monkeypatch.setattr(hook_entry.subprocess, "Popen", popen)
    hook_entry.handle(store, {"host": "codex", "hook_event_name": "SessionStart"})

    assert launched["command"][-2:] == ["distill", "--drain"]
    assert launched["kwargs"]["stdin"] is hook_entry.subprocess.DEVNULL


def test_an_undrained_queue_launches_no_drain_worker(store, monkeypatch):
    drains = []

    hook_entry.handle(
        store,
        {"host": "codex", "hook_event_name": "SessionStart"},
        dream_launch=lambda *_: None,
        drain_launch=lambda _target: drains.append(_target),
    )

    assert drains == []


def test_a_capturing_boundary_offers_no_drain_but_an_empty_one_does(store):
    WriteJobs(store).enqueue("awaiting", "codex")
    drains = []

    hook_entry.handle(
        store,
        {
            "host": "codex",
            "hook_event_name": "Stop",
            "session_id": "boundary",
            "items": ["user: one"],
        },
        launch=lambda *_: True,
        dream_launch=lambda *_: None,
        drain_launch=drains.append,
    )
    hook_entry.handle(
        store,
        {"host": "codex", "hook_event_name": "Stop", "session_id": "boundary", "items": []},
        launch=lambda *_: pytest.fail("an empty boundary launches no distiller"),
        dream_launch=lambda *_: None,
        drain_launch=drains.append,
    )

    assert len(drains) == 1


BLOCKING_HOST = """#!{python}
import os
import time

stop = os.environ["FAKE_HOST_STOP"]
for _ in range(240):
    if os.path.exists(stop):
        raise SystemExit(3)
    time.sleep(0.25)
"""


def _entry(name: str) -> str:
    return str(pathlib.Path(sys.executable).parent / name)


def _json_ask(calls: list[str]):
    def ask(_prompt: str) -> str:
        calls.append(_prompt)
        return json.dumps(_operation())

    return ask


def _real_store(root: pathlib.Path, **jobs) -> Store:
    config = Config.default()
    for knob, value in jobs.items():
        setattr(config.write.jobs, knob, value)
    config.save(root)
    store = Store(root)
    store.init()
    return store


def test_a_killed_worker_leaves_the_job_to_the_next_run(
    tmp_path, monkeypatch, python_executable, capsys
):
    root = tmp_path / "store"
    store = _real_store(root, lease_seconds=1.5, heartbeat_seconds=0.4)
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "claude-code")
    blocking = python_executable(
        tmp_path / "bin-block" / "claude", BLOCKING_HOST.format(python=sys.executable)
    )
    monkeypatch.setenv("PATH", f"{blocking.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_HOST_STOP", str(tmp_path / "stop-host"))
    worker = subprocess.Popen(
        [_entry("mem"), "--store", str(root), "distill", "--job", job.id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    claimed = False
    for _ in range(600):
        if WriteJobs(Store(root)).get(job.id).state == STATE_RUNNING:
            claimed = True
            break
        time.sleep(0.05)
    assert claimed
    worker.kill()
    assert worker.wait(timeout=10) != 0
    (tmp_path / "stop-host").write_text("stop", encoding="utf-8")
    time.sleep(store.config.write.jobs.lease_seconds + 0.6)

    completing = _fake_host(python_executable, tmp_path)
    monkeypatch.setenv("PATH", f"{completing.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv(
        "FAKE_HOST_SCRIPT", json.dumps([[toolkit.TOOL_SUBMIT, {"operations": [_operation()]}]])
    )
    monkeypatch.setenv("FAKE_HOST_LOG", str(tmp_path / "host-log.jsonl"))

    code = main(
        ["--store", str(root), "--json", "distill", "--job", job.id, "--source-host", "claude-code"]
    )

    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "succeeded"
    assert payload["reason"] == "distilled"
    seen = [json.loads(line) for line in (tmp_path / "host-log.jsonl").read_text().splitlines()]
    assert len(seen) == 1
    assert len(Store(root).records()) == 1
    assert WriteJobs(Store(root)).get(job.id).state == STATE_SUCCEEDED
    assert Watermark(store.layout).read("boundary").distilled == 2


def test_a_crash_between_settle_and_complete_is_recovered_by_the_next_run(
    tmp_path, monkeypatch, python_executable, capsys
):
    root = tmp_path / "store"
    store = _real_store(root, lease_seconds=1.0)
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "claude-code")
    first: list[str] = []

    def crash_on_complete(self, job, now=None):
        raise OSError("worker died before it could close the job")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(write_jobs.WriteJobs, "complete", crash_on_complete)
        with pytest.raises(OSError):
            write_run.run_job(store, job.id, _json_ask(first), owner="worker-a")
    assert len(first) == 1
    assert len(store.records()) == 1
    time.sleep(store.config.write.jobs.lease_seconds + 0.2)

    completing = _fake_host(python_executable, tmp_path)
    monkeypatch.setenv("PATH", f"{completing.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv(
        "FAKE_HOST_SCRIPT", json.dumps([[toolkit.TOOL_SUBMIT, {"operations": [_operation()]}]])
    )
    monkeypatch.setenv("FAKE_HOST_LOG", str(tmp_path / "host-log.jsonl"))

    code = main(
        ["--store", str(root), "--json", "distill", "--job", job.id, "--source-host", "claude-code"]
    )

    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason"] == "already distilled"
    assert payload["distilled"] == []
    assert not (tmp_path / "host-log.jsonl").exists()
    assert WriteJobs(Store(root)).get(job.id).state == STATE_SUCCEEDED
    assert len(Store(root).records()) == 1


def test_a_torn_trace_line_never_blocks_recovery_or_the_trace_view(store, cli, clock):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "codex")
    WriteJobs(store).claim("worker-a")
    trace = pathlib.Path(job.trace)
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text('{"event": "run_started"}\n{"eve', encoding="utf-8")
    clock.advance(seconds=store.config.write.jobs.lease_seconds + 1)
    calls: list[str] = []

    payload = write_run.run_job(store, job.id, _json_ask(calls), owner="worker-b")

    assert payload["status"] == "succeeded"
    assert len(calls) == 1
    shown = cli("jobs", "show", job.id, "--trace")
    events = shown["trace"]
    assert [event["event"] for event in events] == [
        "run_started",
        "run_started",
        "batch",
        "round",
        "operations",
        "run_finished",
    ]
    assert events[1]["job"] == job.id
    assert all("messa" not in json.dumps(event) for event in events)


def test_the_host_transport_traces_its_tool_calls_end_to_end(
    store, tmp_path, monkeypatch, python_executable, capsys
):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "claude-code")
    binary = _fake_host(python_executable, tmp_path)
    monkeypatch.setenv("PATH", f"{binary.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv(
        "FAKE_HOST_SCRIPT",
        json.dumps(
            [
                [toolkit.TOOL_RECALL, {"query": "queue timeout"}],
                [toolkit.TOOL_SUBMIT, {"operations": [_operation()]}],
            ]
        ),
    )
    monkeypatch.setenv("FAKE_HOST_LOG", str(tmp_path / "host-log.jsonl"))

    code = main(
        [
            "--store",
            str(store.root),
            "--json",
            "distill",
            "--job",
            job.id,
            "--source-host",
            "claude-code",
        ]
    )

    assert code == EXIT_OK
    trace_lines = pathlib.Path(job.trace).read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in trace_lines]
    kinds = [event["event"] for event in events]
    assert kinds[0] == "run_started"
    assert kinds[-1] == "run_finished"
    assert kinds.count("tool_call") == 2
    assert kinds.count("operations") == 1
    assert "usage" not in kinds
    calls = [event for event in events if event["event"] == "tool_call"]
    assert calls[0]["name"] == toolkit.TOOL_RECALL
    assert "arguments" not in calls[0]
    assert len(calls[0]["digest"]) == 64
    assert calls[0]["length"] > 0
    applied = [event for event in events if event["event"] == "operations"][0]["applied"]
    assert applied == [record.name for record in store.records()]


def test_jobs_show_refuses_an_id_that_could_name_another_file(cli):
    cli("jobs", "show", "../escape", expect=EXIT_INVALID)
    cli("jobs", "retry", "../escape", expect=EXIT_INVALID)
    cli("jobs", "cancel", "../escape", expect=EXIT_INVALID)


def _drain_worker(root: str, owner: str, output) -> None:
    store = Store(root)
    numbers = iter(range(1000000))

    def ask(_prompt: str) -> str:
        number = next(numbers)
        return json.dumps(
            {
                "op": "new",
                "type": "fact",
                "fields": {"project": owner, "subject": f"race-{number}"},
                "abstract": f"Drain {owner} distilled call {number}",
                "provenance": ["0"],
            }
        )

    drained = write_run.drain(store, ask, owner=owner)
    output.put((owner, [item["job"] for item in drained]))


def _hook_enqueue(root: str, session: str, output) -> None:
    store = Store(root)
    capture.capture(store, session, ["user: the race timeout is 30 seconds"], source="pause")
    job = WriteJobs(store).enqueue(session, "codex", trigger_source="hook")
    output.put(("hook", job.id))


FAKE_HOST = """#!{python}
import json, os, subprocess, sys

argv = sys.argv[1:]

def after(flag):
    return argv[argv.index(flag) + 1]

if "--mcp-config" in argv:
    prompt = sys.stdin.read()
    server = next(iter(json.loads(after("--mcp-config"))["mcpServers"].values()))
else:
    raise SystemExit("unexpected claude invocation")

child = subprocess.Popen(
    [server["command"], *server["args"]],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
)

def rpc(request_id, method, params=None):
    message = {{"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {{}}}}
    child.stdin.write(json.dumps(message) + "\\n")
    child.stdin.flush()
    return json.loads(child.stdout.readline())

rpc(0, "initialize")
for index, (name, arguments) in enumerate(json.loads(os.environ["FAKE_HOST_SCRIPT"])):
    rpc(index + 2, "tools/call", {{"name": name, "arguments": arguments}})
child.stdin.close()
child.wait()
with open(os.environ["FAKE_HOST_LOG"], "a", encoding="utf-8") as log:
    record = {{"argv": argv, "executor": os.environ.get("AGENT_MEMORY_EXECUTOR")}}
    log.write(json.dumps(record) + "\\n")
print("done")
"""


def _fake_host(install, tmp_path):
    return install(tmp_path / "bin" / "claude", FAKE_HOST.format(python=sys.executable))


def test_mem_distill_job_runs_one_job_end_to_end_with_the_deterministic_host(
    store, tmp_path, monkeypatch, python_executable, capsys
):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "claude-code")
    binary = _fake_host(python_executable, tmp_path)
    monkeypatch.setenv("PATH", f"{binary.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv(
        "FAKE_HOST_SCRIPT",
        json.dumps([[toolkit.TOOL_SUBMIT, {"operations": [_operation()]}]]),
    )
    monkeypatch.setenv("FAKE_HOST_LOG", str(tmp_path / "host-log.jsonl"))

    code = main(
        [
            "--store",
            str(store.root),
            "--json",
            "distill",
            "--job",
            job.id,
            "--source-host",
            "claude-code",
        ]
    )

    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "succeeded"
    assert payload["distilled"][0]["batches"][0]["written"]
    assert WriteJobs(store).get(job.id).state == STATE_SUCCEEDED
    assert Watermark(store.layout).read("boundary").distilled == 2
    seen = [json.loads(line) for line in (tmp_path / "host-log.jsonl").read_text().splitlines()]
    assert seen[0]["executor"] == "1"


def test_mem_distill_drain_claims_and_runs_every_due_job(
    store, tmp_path, monkeypatch, python_executable, capsys
):
    _capture(store, "first")
    _capture(store, "second")
    WriteJobs(store).enqueue("first", "claude-code")
    store.clock.advance(seconds=1)
    WriteJobs(store).enqueue("second", "claude-code")
    binary = _fake_host(python_executable, tmp_path)
    monkeypatch.setenv("PATH", f"{binary.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv(
        "FAKE_HOST_SCRIPT",
        json.dumps([[toolkit.TOOL_SUBMIT, {"operations": [_operation()]}]]),
    )
    monkeypatch.setenv("FAKE_HOST_LOG", str(tmp_path / "host-log.jsonl"))

    code = main(
        ["--store", str(store.root), "--json", "distill", "--drain", "--source-host", "claude-code"]
    )

    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert [item["session"] for item in payload["drained"]] == ["first", "second"]
    assert all(item["status"] == "succeeded" for item in payload["drained"])
    assert WriteJobs(store).due_count() == 0
    assert Watermark(store.layout).read("first").distilled == 2
    assert Watermark(store.layout).read("second").distilled == 2


def test_mem_distill_drain_stops_when_the_queue_is_empty(cli):
    assert cli("distill", "--drain") == {"drained": []}


def test_mem_jobs_commands_cover_the_whole_lifecycle(cli, clock):
    live = Store(cli.root, clock=clock)
    _capture(live, "first")
    _capture(live, "second")
    queue = WriteJobs(live)
    first = queue.enqueue("first", "codex")
    clock.advance(seconds=1)
    second = queue.enqueue("second", "codex")

    listed = cli("jobs", "list")
    assert [job["id"] for job in listed["jobs"]] == [first.id, second.id]

    shown = cli("jobs", "show", first.id)
    assert shown["session"] == "first"
    assert shown["state"] == STATE_QUEUED
    assert shown["trace"]

    cli("jobs", "cancel", second.id)
    assert cli("jobs", "show", second.id)["state"] == STATE_CANCELLED
    cli("jobs", "retry", second.id)
    assert cli("jobs", "show", second.id)["state"] == STATE_QUEUED

    queue.claim("worker")
    running = cli("jobs", "list", "--state", "running")["jobs"]
    assert [job["id"] for job in running] == [first.id]
    queue.complete(queue.get(first.id))
    collected = cli("jobs", "gc")
    assert collected["jobs"] == 1
    cli("jobs", "show", first.id, expect=EXIT_ERROR)


def test_mem_jobs_list_rejects_an_unknown_state(cli):
    cli("jobs", "list", "--state", "nonsense", expect=EXIT_INVALID)


def test_doctor_reports_an_unhealthy_job_queue(cli, clock):
    live = Store(cli.root, clock=clock)
    _capture(live, "boundary")
    queue = WriteJobs(live)
    queue.enqueue("boundary", "codex")
    current = queue.claim("worker").job
    for _ in range(current.max_attempts):
        current = queue.fail(current, "host unavailable")
        if current.state == STATE_DEAD:
            break
        clock.advance(seconds=live.config.write.jobs.backoff_max_seconds + 1)
        current = queue.claim("worker").job
        assert current is not None

    payload = cli("doctor", "--host", "claude-code", "--no-live", expect=EXIT_ERROR)

    checks = {check["code"]: check for check in payload["checks"]}
    assert checks["WRITE_JOBS_DEGRADED"]["ok"] is False
    assert "1 dead" in checks["WRITE_JOBS_DEGRADED"]["detail"]


def _run_one_job(root: str, job_id: str, owner: str, output) -> None:
    store = Store(root)

    def ask(_prompt: str) -> str:
        return json.dumps(_operation())

    payload = write_run.run_job(store, job_id, ask, owner=owner)
    output.put((owner, payload["status"]))


def test_two_concurrent_claimers_produce_exactly_one_run(tmp_path):
    store = Store(tmp_path / "store")
    store.init()
    capture.capture(store, "boundary", ["user: the queue timeout is 30 seconds"], source="pause")
    job = WriteJobs(store).enqueue("boundary", "codex")
    context = mp.get_context("spawn")
    output = context.Queue()
    workers = [
        context.Process(target=_run_one_job, args=(str(store.root), job.id, owner, output))
        for owner in ("worker-a", "worker-b")
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(30)
        assert worker.exitcode == 0

    results = [output.get(timeout=5) for _ in workers]
    assert sorted(status for _, status in results) == ["skipped", "succeeded"]
    assert len(store.records()) == 1
    assert WriteJobs(store).get(job.id).state == STATE_SUCCEEDED


def _never_reason(_prompt: str) -> str:
    raise AssertionError("a reclaimed run must not reason twice")


def test_a_reclaimed_job_does_not_reason_when_the_watermark_already_settled(store, clock):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "codex")
    WriteJobs(store).claim("worker-1")
    mark = Watermark(store.layout, store.clock).read("boundary")
    Watermark(store.layout, store.clock).settle("boundary", mark.consumed)
    store.clock.advance(seconds=store.config.write.jobs.lease_seconds + 1)

    payload = write_run.run_job(store, job.id, _never_reason, owner="worker-2")

    assert payload["reason"] == "already distilled"


def _hold_distill_lock(root: str, session: str, ready: str, release: str) -> None:
    from agent_memory.core.dreaming import distill_lock_path
    from agent_memory.core.locking import file_lock

    store = Store(root)
    with file_lock(distill_lock_path(store, session), timeout=None):
        pathlib.Path(ready).write_text("ready", encoding="utf-8")
        for _ in range(600):
            if pathlib.Path(release).exists():
                return
            time.sleep(0.05)


def test_an_expired_lease_is_reclaimed_only_when_another_process_released_the_lock(tmp_path):
    store = _real_store(tmp_path / "store", lease_seconds=0.5)
    capture.capture(store, "boundary", ["user: the lock timeout is 30 seconds"], source="pause")
    queue = WriteJobs(store)
    queue.enqueue("boundary", "codex")
    assert queue.claim("worker-a").job is not None
    time.sleep(store.config.write.jobs.lease_seconds + 0.2)
    context = mp.get_context("spawn")
    ready = tmp_path / "lock-ready"
    release = tmp_path / "lock-release"
    holder = context.Process(
        target=_hold_distill_lock,
        args=(str(store.root), "boundary", str(ready), str(release)),
    )
    holder.start()
    for _ in range(200):
        if ready.exists():
            break
        time.sleep(0.05)
    assert ready.exists()

    standing = queue.claim("worker-b")

    assert standing.job is None
    assert standing.reason == "a worker still holds the distill lock"
    assert queue.due_count() == 0

    release.write_text("go", encoding="utf-8")
    holder.join(30)
    assert holder.exitcode == 0
    time.sleep(store.config.write.jobs.lease_seconds + 0.2)

    reclaimed = queue.claim("worker-b")

    assert reclaimed.reason == "reclaimed"
    assert reclaimed.job is not None
    assert reclaimed.job.owner == "worker-b"
    assert reclaimed.job.attempt == 2


def test_concurrent_drains_and_a_hook_enqueue_run_each_job_exactly_once(tmp_path):
    root = str(tmp_path / "store")
    store = Store(tmp_path / "store")
    store.init()
    for session in ("first", "second"):
        capture.capture(store, session, ["user: the race timeout is 30 seconds"], source="pause")
        WriteJobs(store).enqueue(session, "codex")
    context = mp.get_context("spawn")
    output = context.Queue()
    workers = [
        context.Process(target=_drain_worker, args=(root, "drain-a", output)),
        context.Process(target=_drain_worker, args=(root, "drain-b", output)),
        context.Process(target=_hook_enqueue, args=(root, "third", output)),
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(60)
        assert worker.exitcode == 0
    results = [output.get(timeout=10) for _ in workers]

    drained_by = {owner: jobs for owner, jobs in results if owner != "hook"}
    every_run = [job for jobs in drained_by.values() for job in jobs]
    assert len(every_run) == len(set(every_run))
    final = WriteJobs(Store(tmp_path / "store"))
    succeeded = [job.id for job in final.list((STATE_SUCCEEDED,))]
    assert set(succeeded) == set(every_run)
    assert len(Store(tmp_path / "store").records()) == len(succeeded)
    hook_job = next(job for owner, job in results if owner == "hook")
    assert final.get(hook_job).state in (STATE_QUEUED, STATE_SUCCEEDED)
