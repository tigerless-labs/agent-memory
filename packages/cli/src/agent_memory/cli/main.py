"""CLI adapter: argument shape in, core call out, rendering back. No algorithm lives here."""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys
from collections.abc import Sequence

from agent_memory.core import context as context_module
from agent_memory.core import distill as distill_module
from agent_memory.core import (
    dreaming,
    pending,
    portability,
    prompts,
    reasoning,
    sessions,
    stdio,
    triggers,
)
from agent_memory.core import migrate as migrate_module
from agent_memory.core.config import REASONER_ENDPOINT, REASONER_HOST, ExecutorConfig
from agent_memory.core.errors import FieldError, MemoryStoreError, ValidationError
from agent_memory.core.locking import file_lock
from agent_memory.core.manage import Manage
from agent_memory.core.observation import invoke as observe_invocation
from agent_memory.core.reasoning import Reasoner
from agent_memory.core.recall import Recall
from agent_memory.core.store import LEVEL_FULL, LEVELS, Store
from agent_memory.core.watermark import Watermark
from agent_memory.executor import distiller, selection

SESSION_FLAG = "--session"
REASON_HOST = REASONER_HOST
REASON_ENDPOINT = REASONER_ENDPOINT
REASON_NONE = "none"
EMIT_INDENT = 2
FIELD_ERROR_KEYS = frozenset({"field", "reason"})
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INVALID = 2
STDIN_MARKER = "-"


def main(argv: Sequence[str] | None = None) -> int:
    stdio.use_utf8()
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return EXIT_OK
    store = Store(args.store, agent=args.agent)
    try:
        payload = observe_invocation(args.handler, store, args)
    except ValidationError as error:
        _emit(error.as_dict(), args.json, stream=sys.stderr)
        return EXIT_INVALID
    except MemoryStoreError as error:
        _emit(error.as_dict(), args.json, stream=sys.stderr)
        return EXIT_ERROR
    _emit(payload, args.json)
    if (
        args.command in {"setup", "doctor"}
        and isinstance(payload, dict)
        and payload.get("status") == "FAILED"
    ):
        return EXIT_ERROR
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mem", description="agent-memory")
    parser.add_argument("--store", default=None, help="store root (defaults to AGENT_MEMORY_STORE)")
    parser.add_argument("--agent", default="cli", help="calling agent identity")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    subparsers = parser.add_subparsers(dest="command")

    initializer = subparsers.add_parser("init", help="create the store layout")
    initializer.set_defaults(handler=_init)

    writer = subparsers.add_parser("record", help="write one memory")
    writer.add_argument("--abstract", default=None)
    writer.add_argument("--type", default=None)
    writer.add_argument(
        "--field",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="a schema field of the type, e.g. --field project=agent-memory",
    )
    writer.add_argument("--create-group", action="store_true")
    writer.add_argument("--name", default=None)
    writer.add_argument("--body", default="")
    writer.add_argument("--body-file", default=None)
    writer.add_argument("--link", action="append", default=[])
    writer.add_argument("--provenance", action="append", default=[])
    writer.add_argument("--valid-from", default=None)
    writer.add_argument(
        "--batch",
        default=None,
        metavar="FILE|-",
        help="write many memories in one call: one JSON object per line",
    )
    writer.add_argument("--supersedes", default=None)
    writer.set_defaults(handler=_record)

    reader = subparsers.add_parser("recall", help="retrieve an L0 list")
    reader.add_argument("query")
    reader.add_argument("--scope", default=None)
    reader.add_argument("--as-of", default=None)
    reader.add_argument("--limit", type=int, default=None)
    reader.set_defaults(handler=_recall)

    contexter = subparsers.add_parser("context", help="recall and open the top entries in one call")
    contexter.add_argument("query")
    contexter.add_argument("--scope", default=None)
    contexter.add_argument("--as-of", default=None)
    contexter.add_argument("--limit", type=int, default=None)
    contexter.set_defaults(handler=_context)

    opener = subparsers.add_parser("read", help="read one memory")
    opener.add_argument("name")
    opener.add_argument("--level", choices=LEVELS, default=LEVEL_FULL)
    opener.set_defaults(handler=_read)

    corrector = subparsers.add_parser("correct", help="update or supersede one memory")
    corrector.add_argument("name")
    corrector.add_argument("--abstract", default=None)
    corrector.add_argument("--body", default=None)
    corrector.add_argument("--body-file", default=None)
    corrector.add_argument("--supersede-with", default=None)
    correct_links = corrector.add_mutually_exclusive_group()
    correct_links.add_argument(
        "--link",
        action="append",
        default=None,
        help="replace the complete link list; repeat for each retained target",
    )
    correct_links.add_argument(
        "--clear-links", action="store_true", help="replace the link list with an empty list"
    )
    corrector.add_argument("--provenance", action="append", default=[])
    corrector.set_defaults(handler=_correct)

    replacer = subparsers.add_parser(
        "supersede", help="replace an old memory with an existing active memory"
    )
    replacer.add_argument("old")
    replacer.add_argument("new")
    replacer.set_defaults(handler=_supersede)

    merger = subparsers.add_parser("merge", help="combine memories and end their source intervals")
    merger.add_argument("names", nargs="+")
    merger.add_argument("--name", default=None)
    merger.add_argument("--abstract", required=True)
    merger.add_argument("--body", required=True)
    merger.set_defaults(handler=_merge)

    still = subparsers.add_parser(
        "distill", help="hand the archived backlog to the library executor and apply its writes"
    )
    still.add_argument(
        SESSION_FLAG, action="append", default=None, help="a session at a boundary: distill now"
    )
    still.add_argument(
        "--force", action="store_true", help="distill every backlog regardless of thresholds"
    )
    still.add_argument("--reason", choices=(REASON_HOST, REASON_ENDPOINT), default=None)
    still.add_argument(
        "--source-host",
        default="",
        help="host that produced the archived session; used by the default Write policy",
    )
    still.add_argument("--reason-host", default=None)
    still.add_argument("--reason-model", default="")
    still.add_argument("--auto-dream", action="store_true", help=argparse.SUPPRESS)
    still.set_defaults(handler=_distill)

    dreamer = subparsers.add_parser("dream-worker", help=argparse.SUPPRESS)
    dreamer.add_argument("--claim", required=True)
    dreamer.add_argument("--reason", choices=(REASON_HOST, REASON_ENDPOINT), default=None)
    dreamer.add_argument("--reason-host", default=None)
    dreamer.add_argument("--reason-model", default="")
    dreamer.set_defaults(handler=_dream_worker)

    tracer = subparsers.add_parser("trace", help="open the messages a memory cites")
    tracer.add_argument("name")
    tracer.add_argument("--pointer", default=None, help="one cited reference or its subrange")
    tracer.set_defaults(handler=_trace)

    remover = subparsers.add_parser("delete", help="end one memory's validity; retain its history")
    remover.add_argument("name")
    remover.set_defaults(handler=_delete)

    migrator = subparsers.add_parser(
        "migrate", help="upgrade a four-domain store to the schema layout"
    )
    migrator.set_defaults(handler=_migrate)

    voter = subparsers.add_parser("feedback", help="explicit boost or penalty")
    voter.add_argument("name")
    voter.add_argument("--boost", action="store_true")
    voter.add_argument("--penalize", action="store_true")
    voter.set_defaults(handler=_feedback)

    rebuilder = subparsers.add_parser("rebuild", help="drop and rebuild the index")
    rebuilder.set_defaults(handler=_rebuild)

    inspector = subparsers.add_parser("inspect", help="store health")
    inspector.set_defaults(handler=_inspect)

    dream_status = subparsers.add_parser(
        "dream-status", help="show automatic Dream claim, failure, and progress state"
    )
    dream_status.set_defaults(handler=_dream_status)

    exporter = subparsers.add_parser("export", help="export the whole store")
    exporter.add_argument("--out", default=None)
    exporter.add_argument("--no-archive", action="store_true")
    exporter.set_defaults(handler=_export)

    importer = subparsers.add_parser("import", help="import an export into this store")
    importer.add_argument("source")
    importer.set_defaults(handler=_import)

    sleeper = subparsers.add_parser("sleep", help="run the sleep-time Manage pass")
    sleep_due = sleeper.add_mutually_exclusive_group()
    sleep_due.add_argument("--sessions-since", type=int, default=None)
    sleep_due.add_argument(
        "--if-due",
        action="store_true",
        help="run only when persisted, settled session progress satisfies Manage.due()",
    )
    sleeper.add_argument(
        "--trigger-source",
        choices=("cli", "cron"),
        default="cli",
        help="diagnostic source for --if-due (default: cli)",
    )
    sleeper.add_argument(
        "--reason",
        choices=(REASON_HOST, REASON_ENDPOINT, REASON_NONE),
        default=None,
        help="who rules on the open proposals: the configured executor (default), an agent CLI, "
        "a model endpoint, or nobody",
    )
    sleeper.add_argument("--reason-host", default=None)
    sleeper.add_argument("--reason-model", default="")
    sleeper.set_defaults(handler=_sleep)

    cron = subparsers.add_parser("cron", help="manage an opt-in due-aware Dream crontab entry")
    cron_actions = cron.add_subparsers(dest="cron_action", required=True)
    cron_install = cron_actions.add_parser("install", help="install or update this Store's entry")
    cron_install.add_argument(
        "--interval-minutes",
        type=int,
        default=60,
        help="wake-up interval that evenly divides an hour (default: 60)",
    )
    cron_install.add_argument(
        "--mem-path",
        default=None,
        help="absolute path to the mem executable (auto-detected by default)",
    )
    cron_install.add_argument(
        "--log",
        default=None,
        help="append stdout/stderr here (default: STORE/.state/cron.log)",
    )
    cron_install.add_argument(
        "--env-file",
        default=None,
        help="source a mode-600 environment file before running mem",
    )
    cron_install.set_defaults(handler=_cron)
    cron_status = cron_actions.add_parser("status", help="show this Store's entry and scheduler")
    cron_status.set_defaults(handler=_cron)
    cron_remove = cron_actions.add_parser("remove", help="remove only this Store's managed entry")
    cron_remove.set_defaults(handler=_cron)

    proposer = subparsers.add_parser("proposals", help="list proposals awaiting confirmation")
    proposer.set_defaults(handler=_proposals)

    collector = subparsers.add_parser(
        "gc", help="physically remove invalid files; the only deletion entry, human-run"
    )
    collector.set_defaults(handler=_gc)

    decider = subparsers.add_parser("decide", help="confirm or refuse one proposal")
    decider.add_argument("proposal")
    verdict = decider.add_mutually_exclusive_group(required=True)
    verdict.add_argument("--accept", action="store_true")
    verdict.add_argument("--reject", action="store_true")
    decider.add_argument("--text", default="", help="replacement abstract, for an abstract review")
    decider.add_argument("--abstract", default="", help="merged abstract, for a merge")
    decider.add_argument("--body", default="", help="merged body, for a merge")
    decider.add_argument(
        "--parts",
        default=None,
        help="JSON file listing the parts of a split (abstract, body, provenance)",
    )
    decider.set_defaults(handler=_decide)

    skiller = subparsers.add_parser("skill", help="print the agent skill text")
    skiller.set_defaults(handler=_skill)

    installer = subparsers.add_parser("setup", help="configure a host and run preflight")
    installer.add_argument("--host", default=None)
    installer.add_argument("--settings", default=None)
    installer.add_argument("--provider", default=None)
    installer.add_argument("--model", default=None)
    installer.add_argument("--mcp", action="store_true", help="also configure the stdio MCP server")
    installer.add_argument(
        "--no-live", action="store_true", help="skip live reasoner checks (never reports READY)"
    )
    installer.set_defaults(handler=_setup)

    doctor = subparsers.add_parser("doctor", help="diagnose host, Store and provider setup")
    doctor.add_argument("--host", required=True)
    doctor.add_argument("--settings", default=None)
    doctor.add_argument("--provider", default=None)
    doctor.add_argument("--model", default=None)
    doctor.add_argument("--mcp", action="store_true", help="require the stdio MCP server")
    doctor.add_argument(
        "--no-live", action="store_true", help="skip live reasoner checks (never reports READY)"
    )
    doctor.set_defaults(handler=_doctor)

    return parser


def _init(store: Store, args: argparse.Namespace) -> dict[str, object]:
    layout = store.init()
    return {"store": str(layout.root), "types": sorted(store.schemas.load())}


def _record(store: Store, args: argparse.Namespace) -> dict[str, object]:
    if args.batch:
        return _record_batch(store, args.batch)
    missing = [field for field in ("abstract", "type") if not getattr(args, field, None)]
    if missing:
        raise ValidationError([FieldError(field, "required") for field in missing])
    written = store.record(
        abstract=args.abstract,
        type=args.type,
        fields=_fields(args.field),
        body=_body(args.body, args.body_file),
        name=args.name,
        links=args.link,
        create_group=args.create_group,
        valid_from=args.valid_from,
        provenance=args.provenance,
        supersedes=args.supersedes,
    )
    return {
        "name": written.name,
        "path": str(written.path),
        "updated": written.updated,
        "supersedes": args.supersedes,
    }


def _record_batch(store: Store, source: str) -> dict[str, object]:
    text = sys.stdin.read() if source == STDIN_MARKER else pathlib.Path(source).read_text("utf-8")
    specs: list[dict[str, object]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            specs.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValidationError(
                [FieldError(f"line {number}", f"not valid JSON: {error.msg}")]
            ) from error
    return store.record_many(specs).as_dict()


def _recall(store: Store, args: argparse.Namespace) -> dict[str, object]:
    hits = Recall(store).recall(
        args.query, scope=args.scope, as_of=args.as_of, limit=args.limit
    )
    return {
        "query": args.query,
        "recall_fingerprint": store.config.recall_fingerprint(),
        "hits": [hit.as_dict() for hit in hits],
    }


def _context(store: Store, args: argparse.Namespace) -> dict[str, object]:
    built = context_module.build(
        store, args.query, scope=args.scope, as_of=args.as_of, limit=args.limit
    )
    return {
        "query": args.query,
        "entries": built.entries,
        "names": list(built.names),
        "recall_fingerprint": store.config.recall_fingerprint(),
        "text": built.text,
    }


def _read(store: Store, args: argparse.Namespace) -> dict[str, object]:
    result = store.read(args.name, level=args.level)
    return {
        "name": result.record.name,
        "level": result.level,
        "abstract": result.record.abstract,
        "path": str(result.record.path),
        "outline": list(result.outline),
        "text": result.text,
        **({"provenance": list(result.record.provenance)} if args.json else {}),
    }


def _correct(store: Store, args: argparse.Namespace) -> dict[str, object]:
    body = _body(args.body, args.body_file) if (args.body or args.body_file) else None
    corrected = store.correct(
        args.name,
        abstract=args.abstract,
        body=body,
        supersede_with=args.supersede_with,
        links=[] if args.clear_links else args.link,
        provenance=args.provenance,
    )
    return {
        "name": corrected.name,
        "superseded_by": corrected.superseded_by,
        "updated": corrected.updated,
    }


def _supersede(store: Store, args: argparse.Namespace) -> dict[str, object]:
    replaced = store.supersede(args.old, args.new)
    return {"name": replaced.name, "superseded_by": replaced.superseded_by,
            "invalid_at": replaced.invalid_at}


def _merge(store: Store, args: argparse.Namespace) -> dict[str, object]:
    merged = store.merge(args.names, args.abstract, args.body, name=args.name)
    return {"name": merged.name, "path": str(merged.path), "sources": args.names}


def _distill(store: Store, args: argparse.Namespace) -> dict[str, object]:
    watermark = Watermark(store.layout, store.clock)
    named = list(args.session or [])
    candidates = named or sorted(set(watermark.sessions()) | set(_archived_sessions(store)))
    ask = _reasoner(store, args, selection.WRITE, source_host=args.source_host)
    assert ask is not None
    now = store.clock.now().isoformat()
    reports = []
    queue = pending.Pending(store.layout)
    for session in sorted(set(candidates) | set(queue.redistill_sessions())):
        with (
            file_lock(dreaming.distill_lock_path(store, session), timeout=None),
            file_lock(store.layout.maintenance_lock, shared=True, timeout=None),
        ):
            requested = tuple(queue.redistill(session))
            backlog = triggers.backlog(store.layout, session, watermark, requested)
            reason = (
                triggers.REASON_FORCED
                if args.force
                else triggers.reason_for(
                    store.config.write,
                    watermark.read(session),
                    backlog,
                    now,
                    session in named,
                    bool(requested),
                )
            )
            if reason is None:
                continue
            report = distill_module.distill(store, session, backlog, ask)
            queue.clear_redistill(session)
            reports.append({"reason": reason, **report.as_dict()})
    payload: dict[str, object] = {"distilled": reports}
    if args.auto_dream:
        from agent_memory.adapters import auto_dream

        scheduled = auto_dream.launch(store, trigger_source="hook")
        payload["auto_dream"] = {
            "launched": scheduled.claim is not None,
            "due": scheduled.due,
            "trigger_source": "hook",
            "reason": scheduled.reason,
            "sessions_since": scheduled.sessions_since,
            **(
                {
                    "claim": scheduled.claim.id,
                    "reasoner": scheduled.claim.reasoner,
                    "host": scheduled.claim.host,
                }
                if scheduled.claim
                else {}
            ),
        }
    return payload


def _dream_worker(store: Store, args: argparse.Namespace) -> dict[str, object]:
    from agent_memory.adapters import auto_dream

    try:
        reasoner = _reasoner(store, args, selection.MANAGE)
    except Exception as error:
        dreaming.mark_failed(store, args.claim, f"{type(error).__name__}: {error}")
        raise
    return auto_dream.run_worker(store, args.claim, reasoner)


def _archived_sessions(store: Store) -> list[str]:
    folder = store.layout.sessions
    if not folder.is_dir():
        return []
    return [sessions.session_name(path) for path in folder.iterdir() if path.is_file()]


def _trace(store: Store, args: argparse.Namespace) -> dict[str, object]:
    return store.trace_evidence(args.name, args.pointer).as_dict()


def _delete(store: Store, args: argparse.Namespace) -> dict[str, object]:
    removed = store.delete(args.name)
    return {"name": removed.name, "status": removed.status, "invalid_at": removed.invalid_at}


def _migrate(store: Store, args: argparse.Namespace) -> dict[str, object]:
    return migrate_module.migrate(store.root).as_dict()


def _fields(pairs: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator or not key.strip():
            raise ValidationError([FieldError("field", f"expected KEY=VALUE, got {pair}")])
        fields[key.strip()] = value.strip()
    return fields


def _feedback(store: Store, args: argparse.Namespace) -> dict[str, object]:
    step = store.config.weight.boost_step
    delta = (step if args.boost else 0.0) - (step if args.penalize else 0.0)
    updated = store.feedback(args.name, delta)
    return {"name": updated.name, "weight": updated.weight}


def _rebuild(store: Store, args: argparse.Namespace) -> dict[str, object]:
    report = store.rebuild_index()
    return {"reindexed": len(report.reindexed), "dangling_links": len(report.dangling_links)}


def _inspect(store: Store, args: argparse.Namespace) -> dict[str, object]:
    report = store.sync_index()
    records = store.records()
    return {
        "store": str(store.root),
        "active": len([record for record in records if record.is_active()]),
        "total": len(records),
        "invalid": len(store.records(include_invalid=True)) - len(records),
        "dangling_links": [list(pair) for pair in report.dangling_links],
        "unreadable": list(report.unreadable),
        "config_fingerprint": store.config.fingerprint(),
        "recall_fingerprint": store.config.recall_fingerprint(),
    }


def _dream_status(store: Store, args: argparse.Namespace) -> dict[str, object]:
    status = dreaming.state(store)
    complete = set(dreaming.completed_sessions(store))
    raw_covered = status.get("covered_sessions", [])
    covered = {str(item) for item in raw_covered} if isinstance(raw_covered, list) else set()
    return {
        **status,
        "completed_sessions": len(complete),
        "sessions_since": len(complete - covered),
        "write_settled": dreaming.write_is_settled(store),
    }


def _export(store: Store, args: argparse.Namespace) -> dict[str, object]:
    payload = portability.export_store(store, include_archive=not args.no_archive)
    if args.out:
        target = portability.write_export(
            store, pathlib.Path(args.out), include_archive=not args.no_archive
        )
        exported = payload[portability.KEY_FILES]
        count = len(exported) if isinstance(exported, list) else 0
        return {"out": str(target), "files": count}
    return payload


def _import(store: Store, args: argparse.Namespace) -> dict[str, object]:
    written = portability.read_import(store, pathlib.Path(args.source))
    return {"imported": written}


def _sleep(store: Store, args: argparse.Namespace) -> dict[str, object]:
    manage = Manage(store)
    if args.if_due:
        from agent_memory.adapters import auto_dream

        if args.reason == REASON_NONE:
            return auto_dream.run_due(
                store,
                None,
                reasoner_kind=REASON_NONE,
                trigger_source=args.trigger_source,
            )
        executor = _executor(store, args, selection.MANAGE)
        model = executor.host_model if executor.reasoner == REASON_HOST else executor.model
        return auto_dream.run_due(
            store,
            distiller.distiller(executor),
            reasoner_kind=executor.reasoner,
            host=executor.host if executor.reasoner == REASON_HOST else "",
            model=model,
            trigger_source=args.trigger_source,
        )
    if args.sessions_since is not None and not manage.due(args.sessions_since):
        return {"slept": False, "reason": "trigger conditions not met"}
    with (
        file_lock(store.layout.dream_run_lock, timeout=None),
        file_lock(store.layout.maintenance_lock, timeout=None),
    ):
        report = manage.sleep(reasoner=_reasoner(store, args, selection.MANAGE))
    dreaming.record_manual_success(store, report.path)
    return {"slept": True, **report.as_dict()}


def _cron(store: Store, args: argparse.Namespace) -> dict[str, object]:
    from agent_memory.adapters import cron_schedule

    if args.cron_action == "install":
        return cron_schedule.install(
            store,
            interval_minutes=args.interval_minutes,
            mem_path=args.mem_path,
            log_path=args.log,
            env_file=args.env_file,
        )
    if args.cron_action == "status":
        return cron_schedule.status(store)
    return cron_schedule.remove(store)


def _reasoner(
    store: Store,
    args: argparse.Namespace,
    operation: str,
    *,
    source_host: str = "",
) -> Reasoner | None:
    if args.reason == REASON_NONE:
        return None
    return distiller.distiller(_executor(store, args, operation, source_host=source_host))


def _executor(
    store: Store,
    args: argparse.Namespace,
    operation: str,
    *,
    source_host: str = "",
) -> ExecutorConfig:
    return selection.resolve(
        store.config.executor,
        operation,
        source_host=source_host,
        reasoner=args.reason or "",
        host=args.reason_host or "",
        model=args.reason_model,
    )


def _gc(store: Store, args: argparse.Namespace) -> dict[str, object]:
    return {"removed": store.gc()}


def _proposals(store: Store, args: argparse.Namespace) -> dict[str, object]:
    return {"proposals": [proposal.as_dict() for proposal in Manage(store).proposals()]}


def _decide(store: Store, args: argparse.Namespace) -> dict[str, object]:
    parts = json.loads(pathlib.Path(args.parts).read_text(encoding="utf-8")) if args.parts else []
    verdict = reasoning.parse(
        json.dumps(
            {
                "proposal": args.proposal,
                "verdict": reasoning.VERDICT_ACCEPT if args.accept else reasoning.VERDICT_REJECT,
                "text": args.text,
                "abstract": args.abstract,
                "body": args.body,
                "parts": parts,
            }
        )
    )[0]
    decision = Manage(store).decide(args.proposal, accept=args.accept, verdict=verdict)
    return dict(decision.as_dict())


def _skill(store: Store, args: argparse.Namespace) -> str:
    return prompts.skill()


def _setup(store: Store, args: argparse.Namespace) -> dict[str, object]:
    from agent_memory.adapters import host_setup
    from agent_memory.adapters import setup as setup_module

    hosts = [setup_module.canonical_host(args.host)] if args.host else setup_module.detect()
    settings = pathlib.Path(args.settings) if args.settings else None
    if not hosts:
        raise ValidationError([FieldError("host", "no host detected; pass --host")])
    reports = {
        host: host_setup.run(
            store,
            host,
            settings_path=settings,
            provider=args.provider,
            model=args.model,
            mcp=args.mcp,
            live=not args.no_live,
        )
        for host in hosts
    }
    if len(reports) == 1:
        return next(iter(reports.values()))
    failed = any(report["status"] == "FAILED" for report in reports.values())
    status = "FAILED" if failed else "READY"
    return {"status": status, "store": str(store.root), "hosts": reports}


def _doctor(store: Store, args: argparse.Namespace) -> dict[str, object]:
    from agent_memory.adapters import doctor

    return doctor.run(
        store,
        args.host,
        settings_path=pathlib.Path(args.settings) if args.settings else None,
        provider=args.provider,
        model=args.model,
        mcp=args.mcp,
        live=not args.no_live,
    ).as_dict()


def _body(inline: str, from_file: str | None) -> str:
    if from_file == STDIN_MARKER:
        return sys.stdin.read()
    if from_file:
        return pathlib.Path(from_file).read_text(encoding="utf-8")
    return inline


def _emit(payload: object, as_json: bool, stream=None) -> None:
    stream = stream or sys.stdout
    if isinstance(payload, str) and not as_json:
        print(payload, file=stream)
        return
    if as_json or not isinstance(payload, dict):
        rendered = json.dumps(payload, indent=EMIT_INDENT, sort_keys=True, default=_fallback)
        print(rendered, file=stream)
        return
    if "evidence" in payload and "messages" in payload:
        print(f"name: {payload['name']} [{payload['status']}]", file=stream)
        print(payload["notice"], file=stream)
        for warning in payload["warnings"]:
            print(f"warning: {warning}", file=stream)
        for evidence in payload["evidence"]:
            print(f"reference: {evidence['reference']}", file=stream)
            for message in evidence["messages"]:
                print(
                    f"[{message['index']}] {message['role']} @ {message['at']}: {message['text']}",
                    file=stream,
                )
            if evidence["text"] is not None:
                print(evidence["text"], file=stream)
        return
    for key, value in payload.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            print(f"{key}:", file=stream)
            for item in value:
                print(f"  - {_line(item)}", file=stream)
        else:
            print(f"{key}: {value}", file=stream)


def _line(item: dict[str, object]) -> str:
    if frozenset(item) == FIELD_ERROR_KEYS:
        return f"{item['field']}: {item['reason']}"
    name = item.get("name", "")
    abstract = item.get("abstract", "")
    path = item.get("path", "")
    anchor = item.get("anchor") or ""
    score = item.get("score")
    location = f"{path}#{anchor}" if anchor else path
    return f"{name} — {abstract} · {location} · score={score}"


def _fallback(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
