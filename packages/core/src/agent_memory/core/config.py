"""Every tunable in the system. No knob lives anywhere else."""

from __future__ import annotations

import dataclasses
import os
import pathlib
import tomllib

CONFIG_FILENAME = "config.toml"
STORE_ENV_VAR = "AGENT_MEMORY_STORE"
DEFAULT_STORE = "~/agent-memory-store"


@dataclasses.dataclass
class StorageConfig:
    domains: tuple[str, ...] = ("user", "project", "reference", "experience")
    domain_types: dict[str, tuple[str, ...]] = dataclasses.field(
        default_factory=lambda: {
            "user": ("fact", "preference"),
            "project": ("fact", "decision", "procedure"),
            "reference": ("reference",),
            "experience": ("experience", "procedure"),
        }
    )
    max_depth_below_domain: int = 1
    slug_max_length: int = 80
    abstract_max_chars: int = 240
    archive_sessions_enabled: bool = True
    lock_timeout_seconds: float = 30.0
    lock_poll_seconds: float = 0.02


@dataclasses.dataclass
class IndexConfig:
    hash_prefix_length: int = 16
    chunk_min_chars: int = 200
    raw_chunk_chars: int = 1200
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
    demote_penalty: float = 0.5


@dataclasses.dataclass
class RecallConfig:
    default_limit: int = 8
    candidate_pool_multiplier: int = 10
    deep_limit_multiplier: int = 2
    recency_half_life_days: float = 180.0
    recency_decay_base: float = 0.5
    recency_floor: float = 0.25
    retrieval_weight_floor: float = 0.15
    memory_md_weight_floor: float = 0.75
    raw_enabled: bool = True
    raw_relevance_factor: float = 0.4
    synthesis_hint: bool = True
    context_full_text_entries: int = 4
    injection_enabled: bool = True
    injection_budget_bytes: int = 8192
    anchor_context_chars: int = 160
    snippet_max_chars: int = 400


TIER_UNATTENDED = "T0"
TIER_PROPOSAL = "T1"
TIER_HUMAN = "T2"


@dataclasses.dataclass
class ManageConfig:
    authority: str = TIER_UNATTENDED
    trigger_min_hours: float = 24.0
    trigger_min_sessions: int = 3
    cluster_min_files: int = 5
    cluster_min_shared_tokens: int = 2
    stale_after_days: float = 365.0
    merge_proposal_similarity: float = 0.75
    link_cooccurrence_min: int = 2
    abstract_min_words: int = 3
    max_boosts_per_sleep: int = 3
    dream_report_dirname: str = "dream-reports"


@dataclasses.dataclass
class WriteConfig:
    watermark_dirname: str = "watermarks"
    session_archive_enabled: bool = True
    hook_timeout_seconds: float = 20.0
    batch_hint: bool = True


@dataclasses.dataclass
class Config:
    storage: StorageConfig = dataclasses.field(default_factory=StorageConfig)
    index: IndexConfig = dataclasses.field(default_factory=IndexConfig)
    memory_md: MemoryMdConfig = dataclasses.field(default_factory=MemoryMdConfig)
    weight: WeightConfig = dataclasses.field(default_factory=WeightConfig)
    recall: RecallConfig = dataclasses.field(default_factory=RecallConfig)
    manage: ManageConfig = dataclasses.field(default_factory=ManageConfig)
    write: WriteConfig = dataclasses.field(default_factory=WriteConfig)

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
            known = {field.name for field in dataclasses.fields(section)}
            for key, value in values.items():
                if key not in known:
                    raise ValueError(f"unknown config knob: {section_name}.{key}")
                setattr(section, key, value)
        return config

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
                "index": dataclasses.asdict(self.index),
                "recall": dataclasses.asdict(self.recall),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[: self.index.hash_prefix_length]


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
        lines.append(f"[{section_field.name}]")
        for knob in dataclasses.fields(section):
            lines.append(f"{knob.name} = {_render_value(getattr(section, knob.name))}")
        lines.append("")
    return "\n".join(lines)
