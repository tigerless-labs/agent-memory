"""The always-injected root index. A hard budget, enforced by dropping the lightest lines."""

from __future__ import annotations

from .config import Config
from .paths import StoreLayout
from .record import MemoryRecord


def render(records: list[MemoryRecord], config: Config, root: str = "") -> str:
    eligible = [
        record
        for record in records
        if record.is_active() and record.weight >= config.recall.memory_md_weight_floor
    ]
    eligible.sort(key=lambda record: (-record.weight, record.updated, record.name), reverse=False)
    eligible.sort(key=lambda record: record.weight, reverse=True)

    header = config.memory_md.header + "\n\n"
    lines: list[str] = []
    used = len(header.encode("utf-8"))
    for record in eligible:
        if len(lines) >= config.memory_md.max_lines:
            break
        line = _line(record, root)
        cost = len(line.encode("utf-8"))
        if used + cost > config.memory_md.budget_bytes:
            break
        lines.append(line)
        used += cost
    return header + "".join(lines)


def write(layout: StoreLayout, records: list[MemoryRecord]) -> str:
    text = render(records, layout.config, str(layout.root))
    layout.memory_index.write_text(text, encoding="utf-8")
    return text


def _line(record: MemoryRecord, root: str) -> str:
    location = str(record.path)
    if root and location.startswith(root):
        location = location[len(root) :].lstrip("/")
    return f"- [{record.name}]({location}) — {record.abstract}\n"
