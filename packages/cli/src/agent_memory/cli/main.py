"""CLI adapter: argument shape in, core call out, rendering back. No algorithm lives here."""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys
from collections.abc import Sequence

from agent_memory.core import portability
from agent_memory.core.errors import MemoryStoreError, ValidationError
from agent_memory.core.manage import Manage
from agent_memory.core.recall import Recall
from agent_memory.core.store import LEVEL_FULL, LEVELS, Store

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
    writer.add_argument("--abstract", required=True)
    writer.add_argument("--type", required=True)
    writer.add_argument("--domain", required=True)
    writer.add_argument("--name", default=None)
    writer.add_argument("--body", default="")
    writer.add_argument("--body-file", default=None)
    writer.add_argument("--topic", default=None)
    writer.add_argument("--link", action="append", default=[])
    writer.add_argument("--provenance", action="append", default=[])
    writer.add_argument("--valid-from", default=None)
    writer.add_argument("--supersedes", default=None)
    writer.set_defaults(handler=_record)

    reader = subparsers.add_parser("recall", help="retrieve an L0 list")
    reader.add_argument("query")
    reader.add_argument("--scope", default=None)
    reader.add_argument("--as-of", default=None)
    reader.add_argument("--deep", action="store_true")
    reader.add_argument("--limit", type=int, default=None)
    reader.set_defaults(handler=_recall)

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
    sleeper.set_defaults(handler=_sleep)

    installer = subparsers.add_parser("setup", help="install host hooks")
    installer.add_argument("--host", default=None)
    installer.add_argument("--settings", default=None)
    installer.set_defaults(handler=_setup)

    return parser


def _init(store: Store, args: argparse.Namespace) -> dict[str, object]:
    layout = store.init()
    return {"store": str(layout.root), "domains": list(store.config.storage.domains)}


def _record(store: Store, args: argparse.Namespace) -> dict[str, object]:
    written = store.record(
        abstract=args.abstract,
        type=args.type,
        domain=args.domain,
        body=_body(args.body, args.body_file),
        name=args.name,
        links=args.link,
        topic=args.topic,
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


def _recall(store: Store, args: argparse.Namespace) -> dict[str, object]:
    hits = Recall(store).recall(
        args.query, scope=args.scope, as_of=args.as_of, deep=args.deep, limit=args.limit
    )
    return {
        "query": args.query,
        "recall_fingerprint": store.config.recall_fingerprint(),
        "hits": [hit.as_dict() for hit in hits],
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
        "archived": len(store.records(include_archived=True)) - len(records),
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
    return {"slept": True, **manage.sleep().as_dict()}


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
