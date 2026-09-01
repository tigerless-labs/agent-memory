"""Experiment CLI: prepare a suite, run the W matrix, print the report."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import pathlib
import sys
from collections.abc import Sequence

from . import arms as arms_module
from . import dataset, sampling
from . import report as report_module
from .driver import Driver
from .hosts import DEFAULT_MODEL, HOST_CLAUDE_CODE, Host, HostSpec
from .judge import Judge
from .metrics import MetricsSink

EXIT_OK = 0
EXIT_ERROR = 1
DEFAULT_ARMS = "W0,W1,W2,W3,W4"
DEFAULT_SEED = 20260901
JUDGE_MODEL = "claude-sonnet-5"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return EXIT_OK
    return args.handler(args)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mem-exp", description="agent-memory experiments")
    subparsers = parser.add_subparsers(dest="command")

    preparer = subparsers.add_parser("prepare", help="bound a haystack once, on disk")
    preparer.add_argument("--source", required=True)
    preparer.add_argument("--target", required=True)
    preparer.add_argument("--sessions", type=int, required=True)
    preparer.set_defaults(handler=_prepare)

    runner = subparsers.add_parser("run", help="run the W matrix")
    runner.add_argument("--suite", required=True)
    runner.add_argument("--workspace", required=True)
    runner.add_argument("--arms", default=DEFAULT_ARMS)
    runner.add_argument("--per-type", type=int, default=4)
    runner.add_argument("--seed", type=int, default=DEFAULT_SEED)
    runner.add_argument("--sessions-per-call", type=int, default=4)
    runner.add_argument("--model", default=DEFAULT_MODEL)
    runner.add_argument("--judge-model", default=JUDGE_MODEL)
    runner.add_argument("--concurrency", type=int, default=4)
    runner.add_argument("--run-id", default="run")
    runner.set_defaults(handler=_run)

    reporter = subparsers.add_parser("report", help="summarise a finished run")
    reporter.add_argument("--workspace", required=True)
    reporter.add_argument("--json", action="store_true")
    reporter.set_defaults(handler=_report)

    return parser


def _prepare(args: argparse.Namespace) -> int:
    count = dataset.trim(
        pathlib.Path(args.source), pathlib.Path(args.target), args.sessions
    )
    print(json.dumps({"episodes": count, "target": args.target, "sessions": args.sessions}))
    return EXIT_OK


def _run(args: argparse.Namespace) -> int:
    episodes = sampling.stratified(
        dataset.load(pathlib.Path(args.suite)), args.per_type, args.seed
    )
    selected = arms_module.parse(args.arms)
    workspace = pathlib.Path(args.workspace)
    sink = MetricsSink(workspace)
    host = Host(HostSpec(name=HOST_CLAUDE_CODE, binary="claude", model=args.model))
    judge = Judge(Host(HostSpec(name=HOST_CLAUDE_CODE, binary="claude", model=args.judge_model)))
    if not host.spec.available():
        print(json.dumps({"error": f"host binary not found: {host.spec.binary}"}), file=sys.stderr)
        return EXIT_ERROR

    driver = Driver(
        host=host,
        judge=judge,
        workspace=workspace / "stores",
        sessions_per_call=args.sessions_per_call,
        run_id=args.run_id,
        episode_fingerprint=sampling.fingerprint(episodes),
    )
    jobs = [(episode, arm) for arm in selected for episode in episodes]
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(driver.run, episode, arm): (episode, arm) for episode, arm in jobs}
        for future in concurrent.futures.as_completed(futures):
            episode, arm = futures[future]
            record = future.result()
            sink.append(record)
            done += 1
            print(
                f"[{done}/{len(jobs)}] {arm.name} {episode.id} "
                f"{'correct' if record.correct else record.status}",
                file=sys.stderr,
                flush=True,
            )

    print(report_module.render(report_module.summarise(sink.records())))
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
