"""Every tunable in the system. No knob lives anywhere else."""

from __future__ import annotations

import dataclasses
import os
import pathlib
import tomllib
from typing import Any

CONFIG_FILENAME = "config.toml"
STORE_ENV_VAR = "AGENT_MEMORY_STORE"
EXECUTOR_ENV_VAR = "AGENT_MEMORY_EXECUTOR"
MUSE_SETTINGS_ENV_VAR = "AGENT_MEMORY_MUSE_SETTINGS"
REASONER_HOST = "host"
REASONER_ENDPOINT = "endpoint"
TOOL_MODE_AUTO = "auto"
TOOL_MODE_NATIVE = "native"
TOOL_MODE_TEXT = "text"
COORDINATION_LOCK_POLL_SECONDS = 0.02
DREAM_CLAIM_ID_LENGTH = 20
DREAM_ERROR_MAX_CHARS = 1000
STATE_JSON_INDENT = 2
DEFAULT_STORE = "~/agent-memory-store"
LEGACY_KNOBS = {
    "index": frozenset({"raw_chunk_chars"}),
    "recall": frozenset({"deep_limit_multiplier", "raw_enabled", "raw_relevance_factor"}),
    "manage": frozenset({"raw_hit_min"}),
}


@dataclasses.dataclass
class StorageConfig:
    schemas_dirname: str = "schemas"
    max_depth: int = 3
    field_sources: dict[str, str] = dataclasses.field(
        default_factory=lambda: {
            "project": "system",
            "user": "system",
            "date": "system",
            "topic": "menu",
            "category": "menu",
            "source": "menu",
        }
    )
    default_group: str = "general"
    default_project: str = "default"
    default_user: str = "default"
    slug_max_length: int = 80
    abstract_max_chars: int = 240
    archive_sessions_enabled: bool = True
    lock_timeout_seconds: float = 30.0
    lock_poll_seconds: float = 0.02


@dataclasses.dataclass
class IndexConfig:
    hash_prefix_length: int = 16
    chunk_min_chars: int = 200
    bm25_abstract_weight: float = 2.0
    bm25_body_weight: float = 1.0
    vector_enabled: bool = False
    vector_model: str = "BAAI/bge-small-en-v1.5"


@dataclasses.dataclass
class MemoryMdConfig:
    budget_bytes: int = 8192
    max_lines: int = 120
    header: str = "# MEMORY.md"


@dataclasses.dataclass
class WeightConfig:
    initial: float = 1.0
    floor: float = 0.05
    ceiling: float = 5.0
    boost_step: float = 0.5
    decay_step: float = 0.1
    decay_after_days: float = 30.0


@dataclasses.dataclass
class RecallConfig:
    default_limit: int = 8
    candidate_pool_multiplier: int = 10
    recency_half_life_days: float = 180.0
    recency_decay_base: float = 0.5
    recency_floor: float = 0.25
    memory_md_weight_floor: float = 0.75
    synthesis_hint: bool = True
    context_full_text_entries: int = 4
    injection_enabled: bool = True
    injection_budget_bytes: int = 8192
    anchor_context_chars: int = 160
    snippet_max_chars: int = 400


@dataclasses.dataclass
class ManageConfig:
    auto_dream: bool = True
    claim_lease_seconds: float = 1800.0
    trigger_min_hours: float = 24.0
    trigger_min_sessions: int = 3
    cluster_min_files: int = 5
    cluster_min_shared_tokens: int = 2
    merge_proposal_similarity: float = 0.75
    link_cooccurrence_min: int = 2
    abstract_min_words: int = 3
    max_boosts_per_sleep: int = 3
    max_merges_per_sleep: int = 3
    max_supersedes_per_sleep: int = 5
    max_splits_per_sleep: int = 2
    max_deletes_per_sleep: int = 3
    split_min_sections: int = 3
    git_commit: bool = True
    dream_report_dirname: str = "dream-reports"


@dataclasses.dataclass
class WriteConfig:
    watermark_dirname: str = "watermarks"
    session_archive_enabled: bool = True
    hook_timeout_seconds: float = 20.0
    batch_hint: bool = True
    max_distill_input_chars: int = 24000
    reconcile_entries: int = 8
    reconcile_query_chars: int = 2000
    repair_rounds: int = 1
    pending_dirname: str = "pending"
    pending_message_threshold: int = 20
    pending_token_threshold: int = 4000
    chars_per_token: int = 4
    idle_seconds: float = 900.0
    distill_on_boundary: bool = True
    slot_table: bool = True
    event_lane: bool = True
    max_rounds: int = 3
    tool_result_chars: int = 4000


@dataclasses.dataclass
class OperationExecutorConfig:
    reasoner: str = ""
    host: str = ""
    host_provider: str = ""
    host_allow_data_training: bool = False
    host_model: str = ""
    model: str = ""
    endpoint: str = ""
    project: str = ""
    location: str = ""
    timeout_seconds: float = 0.0
    tool_mode: str = ""


@dataclasses.dataclass
class ExecutorConfig:
    reasoner: str = REASONER_HOST
    host: str = "claude-code"
    host_provider: str = ""
    host_allow_data_training: bool = False
    host_model: str = ""
    model: str = "google/gemini-3.7-flash"
    endpoint: str = ""
    project: str = ""
    location: str = "global"
    timeout_seconds: float = 120.0
    tool_mode: str = TOOL_MODE_AUTO
    command: str = "mem distill"
    write: OperationExecutorConfig = dataclasses.field(default_factory=OperationExecutorConfig)
    manage: OperationExecutorConfig = dataclasses.field(default_factory=OperationExecutorConfig)


@dataclasses.dataclass
class Config:
    storage: StorageConfig = dataclasses.field(default_factory=StorageConfig)
    index: IndexConfig = dataclasses.field(default_factory=IndexConfig)
    memory_md: MemoryMdConfig = dataclasses.field(default_factory=MemoryMdConfig)
    weight: WeightConfig = dataclasses.field(default_factory=WeightConfig)
    recall: RecallConfig = dataclasses.field(default_factory=RecallConfig)
    manage: ManageConfig = dataclasses.field(default_factory=ManageConfig)
    write: WriteConfig = dataclasses.field(default_factory=WriteConfig)
    executor: ExecutorConfig = dataclasses.field(default_factory=ExecutorConfig)

    @classmethod
    def default(cls) -> Config:
        return cls()

    @classmethod
    def load(cls, store_root: pathlib.Path) -> Config:
        config = cls.default()
        path = pathlib.Path(store_root) / CONFIG_FILENAME
        if not path.exists():
            return config
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        for section_name, values in raw.items():
            section = getattr(config, section_name, None)
            if section is None or not dataclasses.is_dataclass(section):
                raise ValueError(f"unknown config section: {section_name}")
            _load_section(section, values, section_name)
        config.validate_index()
        return config

    def validate_index(self) -> None:
        if not isinstance(self.index.vector_enabled, bool):
            raise ValueError("index.vector_enabled must be a boolean")
        if not isinstance(self.index.vector_model, str) or not self.index.vector_model.strip():
            raise ValueError("index.vector_model must be a non-empty string")

    def save(self, store_root: pathlib.Path) -> pathlib.Path:
        path = pathlib.Path(store_root) / CONFIG_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_render_toml(self), encoding="utf-8")
        return path

    def fingerprint(self) -> str:
        import hashlib
        import json

        payload = json.dumps(dataclasses.asdict(self), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[: self.index.hash_prefix_length]

    def recall_fingerprint(self) -> str:
        """Hash of only the knobs that shape retrieval — the Invariant 9 drift guard."""
        import hashlib
        import json

        payload = json.dumps(
            {
                "index": self._index_knobs_shaping_recall(),
                "recall": dataclasses.asdict(self.recall),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[: self.index.hash_prefix_length]

    def _index_knobs_shaping_recall(self) -> dict[str, object]:
        knobs = dataclasses.asdict(self.index)
        if not self.index.vector_enabled:
            del knobs["vector_enabled"], knobs["vector_model"]
        return knobs


def resolve_store_root(explicit: str | pathlib.Path | None = None) -> pathlib.Path:
    raw = str(explicit) if explicit else os.environ.get(STORE_ENV_VAR) or DEFAULT_STORE
    return pathlib.Path(raw).expanduser().resolve()


def _render_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_render_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k} = {_render_value(v)}" for k, v in value.items()) + "}"
    return '"' + str(value).replace('"', '\\"') + '"'


def _render_toml(config: Config) -> str:
    lines: list[str] = []
    for section_field in dataclasses.fields(config):
        section = getattr(config, section_field.name)
        _render_section(lines, section_field.name, section)
    return "\n".join(lines)


def _load_section(section: Any, values: object, path: str) -> None:
    if not isinstance(values, dict):
        raise ValueError(f"config section must be a table: {path}")
    known = {field.name for field in dataclasses.fields(section)}
    for key, value in values.items():
        if key in LEGACY_KNOBS.get(path, ()):
            continue
        if key not in known:
            raise ValueError(f"unknown config knob: {path}.{key}")
        current = getattr(section, key)
        if dataclasses.is_dataclass(current):
            _load_section(current, value, f"{path}.{key}")
        elif isinstance(value, dict) and not isinstance(current, dict):
            raise ValueError(f"config knob must not be a table: {path}.{key}")
        elif _has_declared_type(current, value):
            setattr(section, key, value)
        else:
            raise ValueError(f"config knob has the wrong type: {path}.{key}")


def _has_declared_type(current: object, value: object) -> bool:
    if isinstance(current, bool):
        return isinstance(value, bool)
    if isinstance(value, bool):
        return False
    if isinstance(current, int):
        return isinstance(value, int)
    if isinstance(current, float):
        return isinstance(value, int | float)
    if isinstance(current, str):
        return isinstance(value, str)
    return True


def _render_section(lines: list[str], path: str, section: Any) -> None:
    lines.append(f"[{path}]")
    children: list[tuple[str, object]] = []
    for knob in dataclasses.fields(section):
        value = getattr(section, knob.name)
        if dataclasses.is_dataclass(value):
            children.append((knob.name, value))
        else:
            lines.append(f"{knob.name} = {_render_value(value)}")
    lines.append("")
    for name, child in children:
        _render_section(lines, f"{path}.{name}", child)
