# Premise-aware adaptive read: paired 12-case result

This is a privacy-preserving summary. Question text, gold answers, Store contents, session
transcripts, per-question traces, and raw Host output are retained locally and are **not**
part of this public repository.

## Protocol and validity

The baseline and treatment used the same clean code revision
`b3d2e12d20ea36924480b84d10ead939ec11dd55`, the same fixed 12 questions and canonical
Store truth, independent indexed Store copies, Codex `gpt-5.6-sol` as Host and independent
Judge, the same rubric, permissions, 20-turn and 300-second ceilings, and per-arm concurrency
one. The only configured behavior variable was `recall.adaptive_read_enabled` (off/on). The
master switch disables this PR's evidence guidance when off, restoring the mainline agentic
exam policy. Vector was not enabled.

Preflight found nonempty Memory files and indexes, observable Recall candidates, and readable
full bodies for all 12 Store pairs. Source and both arm truth hashes matched for all 12 cases
before and after the runs. A two-case treatment smoke confirmed real Recall and full Read;
the multi-fact case also made a tagged targeted follow-up Recall.

Interruptions and timeouts caused retries. Raw files contain 15 attempts per arm but exactly
12 unique questions per arm. Results below use the **first successful attempt per question
and arm in file order**, independent of correctness. Duplicate successes did not change
treatment correctness outcomes. The local raw records remain available to the owner for
audit, but cannot be independently inspected from this public summary.

## Outcome

| Measure | Baseline | Treatment |
|---|---:|---:|
| Accuracy | **11/12** | **5/12** |
| Recall exposure | 12/12 | 11/12 |
| Full Read exposure | 11/12 | 9/12 |
| Tagged follow-up Recall | 0/12 | 4/12 |
| Full Read after follow-up | 0/12 | 0/12 |
| Empty Recall events | 0 | 2 |
| Mean full memories read | 3.17 | 1.58 |
| Exam latency median | 43.56 s | 48.15 s |
| Exam latency p95 (nearest rank) | 232.22 s | 127.15 s |

Paired outcomes: **0 wrong→right, 6 right→wrong, 5 same-correct, 1 same-wrong**. Treatment
passed the prespecified 6/12 Recall and Read exposure gates, but its second-stage retrieval
never produced a new full Read. Reliable token counts were unavailable.

## Flip analysis

All six flips were right→wrong. They are described without question or Memory contents:

1. A duration from a related but different object was transferred to the object asked about.
   Both arms had the key Memory; the treatment failed fact-level sufficiency.
2. The treatment read two relevant acquisition records but miscounted under the requested
   time scope. The baseline searched more broadly and returned the correct count.
3. A previously recommended resource's exact identity existed in archived session material.
   Baseline deep retrieval reached it; treatment's two non-deep recalls found only unrelated
   distilled Memories and made no full Read.
4. Four previously proposed alternatives existed in an archived session. Baseline deep
   retrieval reached them; treatment's two non-deep recalls were empty and it abstained.
5. Both arms read related Memories about two events. Baseline also had deep Raw candidates
   and answered their order; treatment's follow-up returned repeat Memory hits and it
   abstained without a new full Read.
6. A six-event chronology required broader evidence coverage. Baseline made several deep
   recalls and reads. Treatment stopped at four full reads, then recalled additional hits
   without reading them and gave an incomplete, incorrectly ordered answer.

The baseline already entered the Memory path for this fixed subset. This run therefore does
not support the premise that increasing initial Read exposure improves accuracy here. It
instead provides directional evidence that this **particular bounded, non-deep treatment
policy** regressed on the subset. The main failure modes are loss of archived Raw coverage,
unread follow-up hits, and imperfect fact/time synthesis. A single 12-case live-model replay
is not a broad accuracy estimate or a claim about Vector or the independent Raw Evidence PR.

The earlier 2026-09-14 three-arm evidence-gate run is invalid for feature-effect attribution:
its copied Store indexes were empty and it had no actual Memory exposure. Its scores are not
used here.
