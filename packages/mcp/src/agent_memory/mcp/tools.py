"""The MCP tools. Each one collapses onto the same core call the CLI makes."""

from __future__ import annotations

from agent_memory.core.errors import FieldError, ValidationError
from agent_memory.core.manage import Manage
from agent_memory.core.recall import Recall
from agent_memory.core.store import LEVEL_FULL, LEVELS, Store

TOOL_RECALL = "memory_recall"
TOOL_READ = "memory_read"
TOOL_RECORD = "memory_record"
TOOL_CORRECT = "memory_correct"
TOOL_FEEDBACK = "memory_feedback"
TOOL_PROPOSALS = "memory_proposals"
TOOL_DECIDE = "memory_decide"

DOMAINS = ("user", "project", "reference", "experience")
VERDICT_ACCEPT = "accept"

SCHEMAS: dict[str, dict[str, object]] = {
    TOOL_RECALL: {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "scope": {"type": "string"},
            "as_of": {"type": "string"},
            "deep": {"type": "boolean"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    },
    TOOL_READ: {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "level": {"type": "string", "enum": list(LEVELS)},
        },
        "required": ["name"],
    },
    TOOL_RECORD: {
        "type": "object",
        "properties": {
            "abstract": {"type": "string"},
            "type": {"type": "string"},
            "domain": {"type": "string", "enum": list(DOMAINS)},
            "body": {"type": "string"},
            "name": {"type": "string"},
            "topic": {"type": "string"},
            "links": {"type": "array", "items": {"type": "string"}},
            "provenance": {"type": "array", "items": {"type": "string"}},
            "supersedes": {"type": "string"},
        },
        "required": ["abstract", "type", "domain"],
    },
    TOOL_CORRECT: {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "abstract": {"type": "string"},
            "body": {"type": "string"},
            "supersede_with": {"type": "string"},
        },
        "required": ["name"],
    },
    TOOL_FEEDBACK: {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "direction": {"type": "string", "enum": ["boost", "penalize"]},
        },
        "required": ["name", "direction"],
    },
    TOOL_PROPOSALS: {"type": "object", "properties": {}},
    TOOL_DECIDE: {
        "type": "object",
        "properties": {
            "proposal": {"type": "string"},
            "verdict": {"type": "string", "enum": ["accept", "reject"]},
            "text": {"type": "string"},
        },
        "required": ["proposal", "verdict"],
    },
}

DESCRIPTIONS = {
    TOOL_RECALL: "Search the memory store and return an L0 list of candidates.",
    TOOL_READ: "Read one memory at a chosen level of detail.",
    TOOL_RECORD: "Write one memory into the store.",
    TOOL_CORRECT: "Update a memory in place, or supersede it with a newer one.",
    TOOL_FEEDBACK: "Raise or lower a memory's weight explicitly.",
    TOOL_PROPOSALS: "List the Manage proposals awaiting confirmation.",
    TOOL_DECIDE: "Confirm or refuse one Manage proposal.",
}


def catalogue() -> list[dict[str, object]]:
    return [
        {"name": name, "description": DESCRIPTIONS[name], "inputSchema": SCHEMAS[name]}
        for name in SCHEMAS
    ]


def dispatch(store: Store, tool: str, arguments: dict[str, object]) -> dict[str, object]:
    if tool not in SCHEMAS:
        raise ValidationError([FieldError("tool", f"unknown tool: {tool}")])
    _require(tool, arguments)
    handler = _HANDLERS[tool]
    return handler(store, arguments)


def _require(tool: str, arguments: dict[str, object]) -> None:
    schema = SCHEMAS[tool]
    required = schema.get("required")
    missing = [
        field
        for field in (required if isinstance(required, list) else [])
        if not str(arguments.get(field, "")).strip()
    ]
    if missing:
        raise ValidationError([FieldError(field, "required") for field in missing])
    properties = schema.get("properties")
    for field, rules in (properties if isinstance(properties, dict) else {}).items():
        allowed = rules.get("enum") if isinstance(rules, dict) else None
        value = arguments.get(field)
        if allowed and value is not None and value not in allowed:
            raise ValidationError([FieldError(field, f"must be one of {', '.join(allowed)}")])


def _recall(store: Store, arguments: dict[str, object]) -> dict[str, object]:
    hits = Recall(store).recall(
        str(arguments["query"]),
        scope=_optional(arguments, "scope"),
        as_of=_optional(arguments, "as_of"),
        deep=bool(arguments.get("deep", False)),
        limit=int(str(arguments["limit"])) if arguments.get("limit") else None,
    )
    return {
        "query": str(arguments["query"]),
        "recall_fingerprint": store.config.recall_fingerprint(),
        "hits": [hit.as_dict() for hit in hits],
    }


def _read(store: Store, arguments: dict[str, object]) -> dict[str, object]:
    result = store.read(str(arguments["name"]), level=str(arguments.get("level") or LEVEL_FULL))
    return {
        "name": result.record.name,
        "level": result.level,
        "abstract": result.record.abstract,
        "path": str(result.record.path),
        "outline": list(result.outline),
        "text": result.text,
    }


def _record(store: Store, arguments: dict[str, object]) -> dict[str, object]:
    written = store.record(
        abstract=str(arguments["abstract"]),
        type=str(arguments["type"]),
        domain=str(arguments["domain"]),
        body=str(arguments.get("body") or ""),
        name=_optional(arguments, "name"),
        topic=_optional(arguments, "topic"),
        links=_string_list(arguments.get("links")),
        provenance=_string_list(arguments.get("provenance")),
        supersedes=_optional(arguments, "supersedes"),
    )
    return {"name": written.name, "path": str(written.path), "updated": written.updated}


def _correct(store: Store, arguments: dict[str, object]) -> dict[str, object]:
    corrected = store.correct(
        str(arguments["name"]),
        abstract=_optional(arguments, "abstract"),
        body=_optional(arguments, "body"),
        supersede_with=_optional(arguments, "supersede_with"),
    )
    return {
        "name": corrected.name,
        "superseded_by": corrected.superseded_by,
        "updated": corrected.updated,
    }


def _feedback(store: Store, arguments: dict[str, object]) -> dict[str, object]:
    step = store.config.weight.boost_step
    delta = step if arguments["direction"] == "boost" else -step
    updated = store.feedback(str(arguments["name"]), delta)
    return {"name": updated.name, "weight": updated.weight}


def _optional(arguments: dict[str, object], key: str) -> str | None:
    value = arguments.get(key)
    return str(value) if value is not None and str(value) != "" else None


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _proposals(store: Store, arguments: dict[str, object]) -> dict[str, object]:
    return {"proposals": [proposal.as_dict() for proposal in Manage(store).proposals()]}


def _decide(store: Store, arguments: dict[str, object]) -> dict[str, object]:
    decision = Manage(store).decide(
        str(arguments["proposal"]),
        accept=str(arguments["verdict"]) == VERDICT_ACCEPT,
        text=str(arguments.get("text") or ""),
    )
    return decision.as_dict()


_HANDLERS = {
    TOOL_RECALL: _recall,
    TOOL_READ: _read,
    TOOL_RECORD: _record,
    TOOL_CORRECT: _correct,
    TOOL_FEEDBACK: _feedback,
    TOOL_PROPOSALS: _proposals,
    TOOL_DECIDE: _decide,
}
