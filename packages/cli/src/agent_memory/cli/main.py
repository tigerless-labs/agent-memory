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
from agent_memory.core import migrate as migrate_module
from agent_memory.core import pending, portability, reasoning, sessions, triggers
from agent_memory.core.errors import FieldError, MemoryStoreError, ValidationError
from agent_memory.core.manage import Manage
from agent_memory.core.reasoning import Reasoner
from agent_memory.core.recall import Recall
from agent_memory.core.store import LEVEL_FULL, LEVELS, Store
from agent_memory.core.watermark import Watermark
from agent_memory.executor import distiller, reasoners
from agent_memory.executor.hosts import HOST_CLAUDE_CODE

SESSION_FLAG = "--session"
REASON_HOST = "host"
REASON_ENDPOINT = "endpoint"
EMIT_INDENT = 2
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INVALID = 2
STDIN_MARKER = "-"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return EXIT_OK
    store = Store(args.store, agent=args.agent)
    try:
        payload = args.handler(store, args)
    except ValidationError as error:
        _emit(error.as_dict(), args.json, stream=sys.stderr)
        return EXIT_INVALID
    except MemoryStoreError as error:
        _emit(error.as_dict(), args.json, stream=sys.stderr)
        return EXIT_ERROR
    _emit(payload, args.json)
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
    reader.add_argument("--deep", action="store_true")
    reader.add_argument("--limit", type=int, default=None)
    reader.set_defaults(handler=_recall)

    contexter = subparsers.add_parser("context", help="recall and open the top entries in one call")
    contexter.add_argument("query")
    contexter.add_argument("--scope", default=None)
    contexter.add_argument("--as-of", default=None)
    contexter.add_argument("--deep", action="store_true")
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
    corrector.add_argument("--link", action="append", default=None)
    corrector.add_argument("--provenance", action="append", default=[])
    corrector.set_defaults(handler=_correct)

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
    still.add_argument("--reason-host", default=HOST_CLAUDE_CODE)
    still.add_argument("--reason-model", default="")
    still.set_defaults(handler=_distill)

    tracer = subparsers.add_parser("trace", help="open the messages a memory cites")
    tracer.add_argument("name")
    tracer.set_defaults(handler=_trace)

    remover = subparsers.add_parser("delete", help="mark one memory invalid; the file stays")
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

    exporter = subparsers.add_parser("export", help="export the whole store")
    exporter.add_argument("--out", default=None)
    exporter.add_argument("--no-archive", action="store_true")
    exporter.set_defaults(handler=_export)

    importer = subparsers.add_parser("import", help="import an export into this store")
    importer.add_argument("source")
    importer.set_defaults(handler=_import)

    sleeper = subparsers.add_parser("sleep", help="run the sleep-time Manage pass")
    sleeper.add_argument("--sessions-since", type=int, default=None)
    sleeper.add_argument(
        "--reason",
        choices=(REASON_HOST, REASON_ENDPOINT),
        default=None,
        help="have an agent CLI, or a model endpoint, rule on the open proposals",
    )
    sleeper.add_argument("--reason-host", default=HOST_CLAUDE_CODE)
    sleeper.add_argument("--reason-model", default="")
    sleeper.set_defaults(handler=_sleep)

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

    installer = subparsers.add_parser("setup", help="install host hooks")
    installer.add_argument("--host", default=None)
    installer.add_argument("--settings", default=None)
    installer.set_defaults(handler=_setup)

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
        args.query, scope=args.scope, as_of=args.as_of, deep=args.deep, limit=args.limit
    )
    return {
        "query": args.query,
        "recall_fingerprint": store.config.recall_fingerprint(),
        "hits": [hit.as_dict() for hit in hits],
    }


def _context(store: Store, args: argparse.Namespace) -> dict[str, object]:
    built = context_module.build(
        store, args.query, scope=args.scope, as_of=args.as_of, deep=args.deep, limit=args.limit
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
    }


def _correct(store: Store, args: argparse.Namespace) -> dict[str, object]:
    body = _body(args.body, args.body_file) if (args.body or args.body_file) else None
    corrected = store.correct(
        args.name,
        abstract=args.abstract,
        body=body,
        supersede_with=args.supersede_with,
        links=args.link,
        provenance=args.provenance,
    )
    return {
        "name": corrected.name,
        "superseded_by": corrected.superseded_by,
        "updated": corrected.updated,
    }


def _distill(store: Store, args: argparse.Namespace) -> dict[str, object]:
    watermark = Watermark(store.layout, store.clock)
    named = list(args.session or [])
    candidates = named or sorted(set(watermark.sessions()) | set(_archived_sessions(store)))
    ask = _reasoner(args) or distiller.distiller(store.config.executor)
    now = store.clock.now().isoformat()
    reports = []
    queue = pending.Pending(store.layout)
    for session in sorted(set(candidates) | set(queue.redistill_sessions())):
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
    return {"distilled": reports}


def _archived_sessions(store: Store) -> list[str]:
    folder = store.layout.sessions
    if not folder.is_dir():
        return []
    return [sessions.session_name(path) for path in folder.iterdir() if path.is_file()]


def _trace(store: Store, args: argparse.Namespace) -> dict[str, object]:
    messages = store.trace(args.name)
    return {"name": args.name, "messages": [message.as_dict() for message in messages]}


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
    if args.sessions_since is not None and not manage.due(args.sessions_since):
        return {"slept": False, "reason": "trigger conditions not met"}
    return {"slept": True, **manage.sleep(reasoner=_reasoner(args)).as_dict()}


def _reasoner(args: argparse.Namespace) -> Reasoner | None:
    if args.reason == REASON_HOST:
        return reasoners.HostReasoner.for_host(args.reason_host, model=args.reason_model)
    if args.reason == REASON_ENDPOINT:
        model = args.reason_model or reasoners.DEFAULT_ENDPOINT_MODEL
        return reasoners.EndpointReasoner(model=model)
    return None


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


def _setup(store: Store, args: argparse.Namespace) -> dict[str, object]:
    from agent_memory.adapters import setup as setup_module

    hosts = [args.host] if args.host else setup_module.detect()
    settings = pathlib.Path(args.settings) if args.settings else None
    return {
        "installed": {host: str(setup_module.install(host, settings)) for host in hosts},
        "store": str(store.root),
    }


def _body(inline: str, from_file: str | None) -> str:
    if from_file == STDIN_MARKER:
        return sys.stdin.read()
    if from_file:
        return pathlib.Path(from_file).read_text(encoding="utf-8")
    return inline


def _emit(payload: object, as_json: bool, stream=None) -> None:
    stream = stream or sys.stdout
    if as_json or not isinstance(payload, dict):
        rendered = json.dumps(payload, indent=EMIT_INDENT, sort_keys=True, default=_fallback)
        print(rendered, file=stream)
        return
    for key, value in payload.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            print(f"{key}:", file=stream)
            for item in value:
                print(f"  - {_line(item)}", file=stream)
        else:
            print(f"{key}: {value}", file=stream)


def _line(item: dict[str, object]) -> str:
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
