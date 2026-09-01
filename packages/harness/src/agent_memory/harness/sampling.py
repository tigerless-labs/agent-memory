"""Stratified, seeded subsets. Every arm sees the identical episode list or the run is void."""

from __future__ import annotations

import hashlib

from .dataset import Episode


def stratified(episodes: list[Episode], per_stratum: int, seed: int) -> list[Episode]:
    buckets: dict[str, list[Episode]] = {}
    for episode in episodes:
        buckets.setdefault(episode.question_type, []).append(episode)
    picked: list[Episode] = []
    for stratum in sorted(buckets):
        ordered = sorted(buckets[stratum], key=lambda item: _rank(item.id, seed))
        picked.extend(ordered[:per_stratum])
    return sorted(picked, key=lambda item: (item.question_type, item.id))


def fingerprint(episodes: list[Episode]) -> str:
    payload = "|".join(episode.id for episode in episodes)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:FINGERPRINT_LENGTH]


def _rank(identifier: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{identifier}".encode()).hexdigest()


FINGERPRINT_LENGTH = 16
