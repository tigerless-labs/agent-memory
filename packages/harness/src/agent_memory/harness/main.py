"""Experiment CLI: prepare a suite, run the W matrix, print the report."""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
from collections.abc import Sequence

from agent_memory.core.clock import Clock, FrozenClock
from agent_memory.core.config import Config
from agent_memory.core.manage import Manage
from agent_memory.core.reasoning import Reasoner
from agent_memory.core.store import Store
from agent_memory.executor import reasoners
from agent_memory.executor.hosts import BINARIES, DIALECTS, HOST_CLAUDE_CODE, Host, HostSpec

from . import arms as arms_module
from . import coverage as coverage_module
from . import dataset, locomo, sampling, systems
from . import exam as exam_module
from . import interop as interop_module
from . import judge as judge_module
from . import report as report_module
from . import workspace as workspace_module
from .driver import Driver
from .judge import Judge
from .metrics import STATUS_OK, MetricsSink, RunMetadata, RunMetadataSink

REASON_HOST = "host"
REASON_ENDPOINT = "endpoint"
EXIT_OK = 0
EXIT_ERROR = 1
DEFAULT_ARMS = "W0,W1,W2,W3,W4"
DEFAULT_SEED = 20260901
JUDGE_MODEL = "claude-sonnet-5"
QUESTIONS_FILENAME = "questions.json"
TRUTHY = ("1", "true", "yes", "on")
HOST_PROVIDERS = {"hermes": "gemini"}
PROBE_PROMPT = "Reply with exactly: OK"
PROBE_TOKEN = "OK"
PROBE_TURNS = 3
PROBE_EXCERPT = 120
REACHABILITY = {True: "yes", False: "NO"}
COSTLY_MODEL_MARKERS = ("opus",)
LIMIT_MARKERS = ("session limit", "usage limit", "rate limit", "rate_limit", "overloaded")
ALLOW_COSTLY_ENV = "MEM_EXP_ALLOW_COSTLY_MODEL"
INTEROP_FACT = interop_module.Fact(
    subject="the drain window",
    sentence="The queue drain window must exceed the worker lease TTL by 90 seconds.",
    token="90 seconds",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return EXIT_OK
    try:
        return args.handler(args)
    except workspace_module.DisposableWorkspace as refusal:
        print(json.dumps({"error": str(refusal)}), file=sys.stderr)
        return EXIT_ERROR


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mem-exp", description="agent-memory experiments")
    subparsers = parser.add_subparsers(dest="command")

    preparer = subparsers.add_parser("prepare", help="bound a haystack once, on disk")
    preparer.add_argument("--source", required=True)
    preparer.add_argument("--target", required=True)
    preparer.add_argument("--sessions", type=int, required=True)
    preparer.set_defaults(handler=_prepare)

    converter = subparsers.add_parser(
        "convert-locomo", help="convert a LoCoMo release into a suite the driver replays"
    )
    converter.add_argument("--source", required=True)
    converter.add_argument("--target", required=True)
    converter.set_defaults(handler=_convert_locomo)

    runner = subparsers.add_parser("run", help="run the W matrix")
    runner.add_argument("--suite", required=True)
    runner.add_argument("--workspace", required=True)
    runner.add_argument("--arms", default=DEFAULT_ARMS)
    runner.add_argument("--per-type", type=int, default=4)
    runner.add_argument("--seed", type=int, default=DEFAULT_SEED)
    runner.add_argument("--sessions-per-call", type=int, default=1)
    runner.add_argument("--experience-workers", type=int, default=4)
    runner.add_argument("--exam-max-turns", type=int, default=20)
    runner.add_argument("--exam-mode", choices=exam_module.MODES, default=exam_module.MODE_AGENTIC)
    runner.add_argument(
        "--reuse-stores", default=None,
        help="replay against another run's stores; skips the experience phase entirely",
    )
    runner.add_argument(
        "--set", action="append", default=[], metavar="SECTION.KNOB=VALUE",
        help="override one config knob for every run in this matrix",
    )
    runner.add_argument("--host", default=HOST_CLAUDE_CODE, choices=sorted(DIALECTS))
    runner.add_argument(
        "--system", default=systems.NATIVE, choices=systems.NAMES,
        help="the memory system under test; memcore reads its checkout from MEMCORE_HOME",
    )
    runner.add_argument("--model", default="")
    runner.add_argument("--judge-model", default=JUDGE_MODEL)
    runner.add_argument("--concurrency", type=int, default=4)
    runner.add_argument("--run-id", default="run")
    runner.add_argument(
        "--manage", default="",
        help="label the sleep these stores went through, so the report can compare sleeps",
    )
    runner.add_argument(
        "--resume", action="store_true",
        help="keep this workspace's successful records and run only the rest",
    )
    runner.set_defaults(handler=_run)

    regrader = subparsers.add_parser(
        "regrade", help="re-judge stored answers without re-running the hosts"
    )
    regrader.add_argument("--workspace", required=True)
    regrader.add_argument("--judge-model", default=JUDGE_MODEL)
    regrader.add_argument("--concurrency", type=int, default=8)
    regrader.set_defaults(handler=_regrade)

    calibrator = subparsers.add_parser(
        "calibrate", help="check the judge against hand-labelled cases"
    )
    calibrator.add_argument("--cases", required=True)
    calibrator.add_argument("--judge-model", default=JUDGE_MODEL)
    calibrator.add_argument("--concurrency", type=int, default=8)
    calibrator.set_defaults(handler=_calibrate)

    prober = subparsers.add_parser(
        "hosts", help="which hosts are installed, and which can actually answer right now"
    )
    prober.add_argument("--probe", action="store_true", help="send each host one live prompt")
    prober.add_argument("--json", action="store_true")
    prober.set_defaults(handler=_hosts)

    interoperator = subparsers.add_parser(
        "interop", help="one store, several hosts: what A writes, B must read"
    )
    interoperator.add_argument("--workspace", required=True)
    interoperator.add_argument("--hosts", default=",".join(DIALECTS))
    interoperator.add_argument("--json", action="store_true")
    interoperator.set_defaults(handler=_interop)

    sleeper = subparsers.add_parser(
        "sleep-stores", help="copy a store tree and run sleep-time Manage over every store"
    )
    sleeper.add_argument("--stores", required=True)
    sleeper.add_argument("--target", required=True)
    sleeper.add_argument(
        "--days-later", type=float, default=0.0,
        help="sleep as if this many days have passed, so decay and staleness can fire",
    )
    sleeper.add_argument("--reason", choices=(REASON_HOST, REASON_ENDPOINT), default=None)
    sleeper.add_argument("--reason-host", default=HOST_CLAUDE_CODE)
    sleeper.add_argument("--reason-model", default="")
    sleeper.add_argument(
        "--set", action="append", default=[], metavar="SECTION.KNOB=VALUE",
        help="override one config knob for every store this step sleeps",
    )
    sleeper.set_defaults(handler=_sleep_stores)

    prober_coverage = subparsers.add_parser(
        "coverage", help="offline: did the gold answer reach any record a run wrote?"
    )
    prober_coverage.add_argument("--workspace", required=True)
    prober_coverage.add_argument(
        "--stores", default=None, help="store tree to read; defaults to <workspace>/stores"
    )
    prober_coverage.add_argument(
        "--threshold", type=float, default=coverage_module.DEFAULT_THRESHOLD
    )
    prober_coverage.add_argument("--json", action="store_true")
    prober_coverage.set_defaults(handler=_coverage)

    reporter = subparsers.add_parser("report", help="summarise a finished run")
    reporter.add_argument("--workspace", required=True)
    reporter.add_argument("--json", action="store_true")
    reporter.set_defaults(handler=_report)

    return parser


def _prepare(args: argparse.Namespace) -> int:
    count = dataset.trim(
        pathlib.Path(args.source), workspace_module.for_writing(args.target), args.sessions
    )
    print(json.dumps({"episodes": count, "target": args.target, "sessions": args.sessions}))
    return EXIT_OK


def _convert_locomo(args: argparse.Namespace) -> int:
    target = workspace_module.for_writing(args.target)
    count = locomo.convert(pathlib.Path(args.source), target)
    print(json.dumps({"episodes": count, "target": str(target)}))
    return EXIT_OK


def _run(args: argparse.Namespace) -> int:
    episodes = sampling.stratified(
        dataset.load(pathlib.Path(args.suite)), args.per_type, args.seed
    )
    selected = arms_module.parse(args.arms)
    workspace = workspace_module.for_writing(args.workspace)
    sink = MetricsSink(workspace)
    host = _host(args.host, args.model)
    judge = Judge(
        Host(
            HostSpec(
                name=HOST_CLAUDE_CODE, binary="claude",
                model=_affordable(args.judge_model, "judge"),
            )
        )
    )
    if not host.spec.available():
        print(json.dumps({"error": f"host binary not found: {host.spec.binary}"}), file=sys.stderr)
        return EXIT_ERROR

    config = _configured(args.set)
    episode_fingerprint = sampling.fingerprint(episodes)
    RunMetadataSink(workspace).ensure(
        RunMetadata(
            run_id=args.run_id,
            system=args.system,
            host=host.name,
            model=host.spec.model,
            judge_model=judge.model,
            exam_mode=args.exam_mode,
            episode_fingerprint=episode_fingerprint,
            reuse_stores=args.reuse_stores or None,
            config=dataclasses.asdict(config),
            code_revision=_code_revision(),
        ),
        resume=args.resume,
    )
    (workspace / QUESTIONS_FILENAME).write_text(
        json.dumps({episode.id: episode.question for episode in episodes}, sort_keys=True),
        encoding="utf-8",
    )
    driver = Driver(
        host=host,
        judge=judge,
        workspace=workspace / "stores",
        sessions_per_call=args.sessions_per_call,
        experience_workers=args.experience_workers,
        exam_max_turns=args.exam_max_turns,
        exam_mode=args.exam_mode,
        config=config,
        reuse_stores=pathlib.Path(args.reuse_stores) if args.reuse_stores else None,
        run_id=args.run_id,
        manage=args.manage,
        episode_fingerprint=episode_fingerprint,
        system=systems.build(args.system, config),
    )
    jobs = [(episode, arm) for arm in selected for episode in episodes]
    if args.resume:
        jobs = _resumable(sink, jobs, episode_fingerprint, args.system)
    halted = _execute(driver, jobs, sink, args.concurrency)
    if halted:
        print(
            json.dumps({"halted": halted, "recorded": len(sink.records()), "of": len(jobs)}),
            file=sys.stderr,
        )
    print(report_module.render(report_module.summarise(sink.records())))
    return EXIT_ERROR if halted else EXIT_OK


def _execute(driver: Driver, jobs: list, sink: MetricsSink, concurrency: int) -> str:
    """A quota failure is an environment failure, not a measurement: the matrix stops
    there, with what was measured kept, rather than recording every remaining episode
    as failed. Returns the reason it stopped, or nothing when it ran to the end."""
    halted = ""
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(driver.run, episode, arm): (episode, arm) for episode, arm in jobs}
        for future in concurrent.futures.as_completed(futures):
            episode, arm = futures[future]
            record = future.result()
            sink.append(record)
            print(
                f"[{len(sink.records())}/{len(jobs)}] {arm.name} {episode.id} "
                f"{'correct' if record.correct else record.status}",
                file=sys.stderr,
                flush=True,
            )
            if _hit_limit(record.error):
                halted = record.error
                pool.shutdown(wait=True, cancel_futures=True)
                break
    return halted


def _hit_limit(error: str) -> bool:
    lowered = error.lower()
    return any(marker in lowered for marker in LIMIT_MARKERS)


def _code_revision(run=subprocess.run) -> str:
    try:
        completed = run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        )
    except OSError:
        return "unknown"
    revision = completed.stdout.strip()
    return revision if completed.returncode == 0 and revision else "unknown"


def _resumable(sink: MetricsSink, jobs: list, episode_fingerprint: str, system: str) -> list:
    """Keep what succeeded, drop what failed, and run only what is not yet succeeded —
    on the same episode set and the same system, or the records would not be one run."""
    existing = sink.records()
    fingerprints = {str(record["episode_fingerprint"]) for record in existing}
    if fingerprints - {episode_fingerprint}:
        raise ValueError("resume refused: the workspace holds another episode set")
    recorded_systems = {str(record.get("system", systems.NATIVE)) for record in existing}
    if recorded_systems - {system}:
        raise ValueError("resume refused: the workspace holds another memory system")
    succeeded = [record for record in existing if record["status"] == STATUS_OK]
    sink.replace(succeeded)
    done = {(str(record["arm"]), str(record["episode_id"])) for record in succeeded}
    return [(episode, arm) for episode, arm in jobs if (arm.name, episode.id) not in done]


def _configured(overrides: list[str]) -> Config:
    """W options are config (ADR-006), so an experiment arm is a knob, never a code branch."""
    config = Config.default()
    for override in overrides:
        path, _, raw = override.partition("=")
        section_name, _, knob = path.partition(".")
        section = getattr(config, section_name, None)
        if section is None or not hasattr(section, knob):
            raise ValueError(f"unknown config knob: {path}")
        setattr(section, knob, _coerce(getattr(section, knob), raw))
    return config


def _coerce(current: object, raw: str) -> object:
    if isinstance(current, bool):
        return raw.strip().lower() in TRUTHY
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    return raw


def _regrade(args: argparse.Namespace) -> int:
    workspace = workspace_module.for_writing(args.workspace)
    sink = MetricsSink(workspace)
    records = sink.records()
    judge = Judge(
        Host(
            HostSpec(
                name=HOST_CLAUDE_CODE, binary="claude",
                model=_affordable(args.judge_model, "judge"),
            )
        )
    )
    regraded = judge_module.regrade(records, judge, _questions(workspace), args.concurrency)
    changed = sum(1 for old, new in zip(records, regraded, strict=True) if old != new)
    sink.replace(regraded)
    print(f"regraded {len(regraded)} records, {changed} changed", file=sys.stderr)
    print(report_module.render(report_module.summarise(regraded)))
    return EXIT_OK


def _questions(workspace: pathlib.Path) -> dict[str, str]:
    manifest = workspace / QUESTIONS_FILENAME
    if not manifest.exists():
        raise FileNotFoundError(f"no question manifest at {manifest}")
    return json.loads(manifest.read_text(encoding="utf-8"))


def _calibrate(args: argparse.Namespace) -> int:
    """An instrument that has not been checked against known answers is not a measurement."""
    cases = json.loads(pathlib.Path(args.cases).read_text(encoding="utf-8"))
    judge = Judge(
        Host(
            HostSpec(
                name=HOST_CLAUDE_CODE, binary="claude",
                model=_affordable(args.judge_model, "judge"),
            )
        )
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        verdicts = list(
            pool.map(
                lambda case: judge.grade(case["question"], case["expected"], case["candidate"]),
                cases,
            )
        )
    wrong = [
        case["case"]
        for case, verdict in zip(cases, verdicts, strict=True)
        if verdict.correct != case["label"]
    ]
    agreed = len(cases) - len(wrong)
    print(f"judge {args.judge_model}: {agreed}/{len(cases)} agree with the labels")
    for name in wrong:
        print(f"  disagrees: {name}")
    return EXIT_OK if not wrong else EXIT_ERROR


def _hosts(args: argparse.Namespace) -> int:
    """Availability is data, not an assumption: a host that cannot answer is reported, and a
    run that excludes it says so rather than quietly measuring one host less."""
    findings: list[dict[str, object]] = []
    for name in sorted(DIALECTS):
        host = _host(name)
        installed = host.spec.available()
        reachable: bool | None = None
        detail = ""
        if args.probe and installed:
            result = host.run(PROBE_PROMPT, tools_enabled=False, max_turns=PROBE_TURNS)
            reachable = result.ok and PROBE_TOKEN in result.text.upper()
            detail = (result.error or result.text)[:PROBE_EXCERPT]
        findings.append(
            {
                "host": name,
                "binary": host.spec.binary,
                "model": host.spec.model,
                "installed": installed,
                "reachable": reachable,
                "detail": detail,
            }
        )
    if args.json:
        print(json.dumps(findings, indent=REPORT_INDENT))
        return EXIT_OK
    print("| host | installed | reachable | detail |")
    print("|---|---|---|---|")
    for entry in findings:
        lines = str(entry["detail"]).splitlines()
        probed = entry["reachable"]
        cell = "-" if probed is None else REACHABILITY[probed is True]
        print(
            f"| {entry['host']} | {'yes' if entry['installed'] else 'NO'} "
            f"| {cell} | {lines[0] if lines else ''} |"
        )
    return EXIT_OK


def _interop(args: argparse.Namespace) -> int:
    hosts = [_host(name) for name in args.hosts.split(",") if name.strip()]
    missing = [host.name for host in hosts if not host.spec.available()]
    if missing:
        print(json.dumps({"error": "host binaries not found", "hosts": missing}), file=sys.stderr)
        return EXIT_ERROR
    results = interop_module.matrix(
        hosts, INTEROP_FACT, workspace_module.for_writing(args.workspace)
    )
    if args.json:
        print(json.dumps([result.as_dict() for result in results], indent=REPORT_INDENT))
    else:
        print(interop_module.render(results))
    return EXIT_OK if all(result.passed for result in results) else EXIT_ERROR


def _affordable(model: str, role: str) -> str:
    """A matrix is hundreds of calls, so the expensive tier has to be asked for out loud."""
    lowered = model.lower()
    hit = [marker for marker in COSTLY_MODEL_MARKERS if marker in lowered]
    if hit and not os.environ.get(ALLOW_COSTLY_ENV):
        raise ValueError(
            f"{role} model {model!r} is the expensive tier; "
            f"set {ALLOW_COSTLY_ENV}=1 to run it deliberately"
        )
    return model


def _host(name: str, model: str = "", attempts: int = 1) -> Host:
    """Model and provider come from the environment so a host is added without a code change."""
    binary, default_model = BINARIES[name]
    return Host(
        HostSpec(
            name=name,
            binary=binary,
            model=_affordable(model or os.environ.get(_model_env(name)) or default_model, name),
            provider=os.environ.get(_provider_env(name), HOST_PROVIDERS.get(name, "")),
            attempts=attempts,
        )
    )


def _model_env(name: str) -> str:
    return name.replace("-", "_").upper() + "_MODEL"


def _provider_env(name: str) -> str:
    return name.replace("-", "_").upper() + "_PROVIDER"


def _sleep_stores(args: argparse.Namespace) -> int:
    """Copy first: the un-slept arm has to survive as the control."""
    source = pathlib.Path(args.stores)
    target = workspace_module.for_writing(args.target)
    if target.exists():
        raise FileExistsError(f"{target} already exists")
    shutil.copytree(source, target)

    clock = _clock_at(args.days_later)
    reasoner = _reasoner(args)
    tally = {"stores": 0, "actions": 0, "proposals": 0, "decisions": 0, "withheld": 0}
    for root in sorted(path for path in target.rglob("MEMORY.md")):
        store = Store(root.parent, config=_configured(args.set), clock=clock, agent="sleep")
        report = Manage(store, clock).sleep(reasoner=reasoner)
        tally["stores"] += 1
        tally["actions"] += len(report.actions)
        tally["proposals"] += len(report.proposals)
        tally["decisions"] += len(report.decisions)
        tally["withheld"] += len(report.withheld)
    print(json.dumps({**tally, "target": str(target)}, sort_keys=True))
    return EXIT_OK


def _reasoner(args: argparse.Namespace) -> Reasoner | None:
    """The experiment's own borrowed intelligence, spoken to exactly as the CLI speaks to it."""
    if args.reason == REASON_HOST:
        return reasoners.HostReasoner(host=_host(args.reason_host, args.reason_model))
    if args.reason == REASON_ENDPOINT:
        model = args.reason_model or reasoners.DEFAULT_ENDPOINT_MODEL
        return reasoners.EndpointReasoner(model=model)
    return None


def _clock_at(days_later: float):
    """Value-based forgetting is a function of elapsed time; a same-day store has nothing to
    forget. Advancing the clock is how the staleness curve becomes measurable at all."""
    if days_later <= 0:
        return None
    return FrozenClock(Clock().now() + datetime.timedelta(days=days_later))


def _coverage(args: argparse.Namespace) -> int:
    """Deterministic, so one pass is a result; offline, so it costs no host call."""
    workspace = pathlib.Path(args.workspace)
    stores = pathlib.Path(args.stores) if args.stores else workspace / "stores"
    rows = coverage_module.probe(MetricsSink(workspace).records(), stores, args.threshold)
    print(coverage_module.as_json(rows) if args.json else coverage_module.render(rows))
    return EXIT_OK


def _report(args: argparse.Namespace) -> int:
    sink = MetricsSink(pathlib.Path(args.workspace))
    summary = report_module.summarise(sink.records())
    if args.json:
        print(
            json.dumps(
                {
                    "arms": [arm.__dict__ for arm in summary.arms],
                    "by_question_type": summary.by_question_type,
                    "attribution_licensed": summary.attribution_is_licensed(),
                },
                indent=REPORT_INDENT,
                sort_keys=True,
            )
        )
        return EXIT_OK
    print(report_module.render(summary))
    return EXIT_OK


REPORT_INDENT = 2


if __name__ == "__main__":
    raise SystemExit(main())
