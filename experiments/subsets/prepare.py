"""Offline frozen-corpus manifest preparation; never imports a host or runner."""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'packages/harness/src'))
from agent_memory.harness import dataset, sampling  # noqa: E402

SEED = 20260901
SUITE = 'experiments/data/longmemeval_s12.json'
CORPUS = 'experiments/runs/p4sup/stores'
RECORDS = 'experiments/runs/p4sup/runs.jsonl'
DEFAULT = ROOT / 'experiments/subsets/p4sup-seed20260901.json'


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False
    ).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    suite = dataset.load(ROOT / SUITE)
    if len({e.id for e in suite}) != len(suite):
        raise ValueError('duplicate suite question IDs')
    records = [json.loads(line) for line in (ROOT / RECORDS).read_text().splitlines()]
    selected = sampling.stratified(suite, 20, SEED)
    ids = {e.id for e in selected}
    if len(records) != 120 or {r['episode_id'] for r in records} != ids:
        raise ValueError('source records do not match the frozen 120-question selection')
    if {r['episode_fingerprint'] for r in records} != {sampling.fingerprint(selected)}:
        raise ValueError('source episode fingerprint mismatch')
    by_id = {e.id: e for e in selected}
    if any(r['arm'] != 'W2' or r['question_type'] != by_id[r['episode_id']].question_type
           for r in records):
        raise ValueError('source arm/type mismatch')
    if {p.name for p in (ROOT / CORPUS / 'W2').iterdir() if p.is_dir()} != ids:
        raise ValueError('Store directory IDs mismatch')
    # Git-tracked files are the repository-defined frozen truth, excluding rebuildable caches.
    paths = subprocess.check_output(
        ['git', 'ls-files', '-z', '--', CORPUS], cwd=ROOT
    ).decode().split('\0')
    truth = {}
    for name in sorted(filter(None, paths)):
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'missing or symlinked truth: {name}')
        truth[path.relative_to(ROOT / CORPUS).as_posix()] = file_hash(path)
    stores = {}
    for identifier in sorted(ids):
        prefix = f'W2/{identifier}/'
        files = {p[len(prefix):]: h for p, h in truth.items() if p.startswith(prefix)}
        if not files:
            raise ValueError(f'no tracked Store truth for {identifier}')
        stores[identifier] = {'path': f'{CORPUS}/W2/{identifier}',
                              'truth_sha256': digest(files), 'files': files}
    buckets = {}
    # Recover the fixed order via nested prefixes of the EXISTING sampler. No second RNG.
    for kind in sorted({e.question_type for e in selected}):
        bucket = [e for e in selected if e.question_type == kind]
        if len(bucket) != 20:
            raise ValueError(f'unexpected bucket distribution: {kind}={len(bucket)}')
        order, seen = [], set()
        for n in range(1, len(bucket) + 1):
            prefix = {e.id for e in sampling.stratified(bucket, n, SEED)}
            added = prefix - seen
            if len(added) != 1 or not seen <= prefix:
                raise ValueError('sampler no longer produces nested prefixes')
            order.extend(sorted(added))
            seen = prefix
        buckets[kind] = order
    if len(buckets) != 6:
        raise ValueError('expected six verified buckets; replan before generating')
    stages, cumulative = [], []
    previous = 0
    for n in (2, 4, 8, 16, 20):
        added = [buckets[k][i] for i in range(previous, n) for k in buckets]
        cumulative = cumulative + added
        canonical = sorted((by_id[q] for q in cumulative), key=lambda e: (e.question_type, e.id))
        stages.append({'total': len(cumulative), 'per_type': n, 'added_count': len(added),
                       'added_question_ids': added, 'cumulative_question_ids': cumulative,
                       'ordered_ids_sha256': digest(cumulative),
                       'harness_episode_fingerprint': sampling.fingerprint(canonical)})
        previous = n
    manifest = {
        'schema_version': 1, 'seed': SEED,
        'source_suite': {'path': SUITE, 'sha256': file_hash(ROOT / SUITE),
                         'total_episodes': len(suite)},
        'source_store_corpus': {'path': CORPUS, 'arm': 'W2', 'truth_scope':
                               'git-tracked files only; cache/index/state excluded by repository',
                               'truth_sha256': digest(truth), 'stores': stores},
        'source_records': {'path': RECORDS, 'sha256': file_hash(ROOT / RECORDS)},
        'source_episode_fingerprint': sampling.fingerprint(selected),
        'episode_content_sha256': {e.id: digest(dataclasses.asdict(e)) for e in selected},
        'preparation_code_revision': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'preparation_source_sha256': {p: file_hash(ROOT / p) for p in (
            'experiments/subsets/prepare.py',
            'packages/harness/src/agent_memory/harness/sampling.py',
            'packages/harness/src/agent_memory/harness/dataset.py')},
        'algorithm': 'existing stratified SHA256(seed:id) prefixes; sorted types; round-robin ranks',
        'bucket_orders': buckets, 'stages': stages,
        'shared_by': ['Baseline', 'Progressive Read', 'Virtual Overview'],
    }
    manifest['manifest_sha256'] = digest(manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='read-only verification of frozen manifest')
    parser.add_argument('--output', type=pathlib.Path, default=DEFAULT)
    args = parser.parse_args()
    actual = build()
    if args.check:
        expected = json.loads(args.output.read_text())
        # A later checkout may have a different HEAD; the preparation source hashes remain checked.
        actual['preparation_code_revision'] = expected['preparation_code_revision']
        actual.pop('manifest_sha256')
        actual['manifest_sha256'] = digest(actual)
        if actual != expected:
            raise SystemExit('manifest/source mismatch; do not reuse results or overwrite the manifest')
        print('Verified manifest, nested IDs, episode content and all tracked Store truth bytes.')
    else:
        with args.output.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(actual, indent=2, ensure_ascii=False) + '\n')
        print(args.output)


if __name__ == '__main__':
    main()
