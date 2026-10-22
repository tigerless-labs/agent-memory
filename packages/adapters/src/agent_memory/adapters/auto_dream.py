"""Detached automatic Dream launcher and one-shot worker."""

from __future__ import annotations

import os
import subprocess

from agent_memory.core import dreaming
from agent_memory.core.config import (
    EXECUTOR_ENV_VAR,
    REASONER_ENDPOINT,
    REASONER_HOST,
    STORE_ENV_VAR,
)
from agent_memory.core.errors import LockTimeoutError
from agent_memory.core.locking import file_lock
from agent_memory.core.manage import Manage
from agent_memory.core.reasoning import Reasoner
from agent_memory.core.store import Store

from . import detached

LOG_FILENAME = "hooks.log"
EXECUTABLE = "mem"
COMMAND = "dream-worker"
CLAIM_FLAG = "--claim"
REASON_HOST_FLAG = "--reason-host"
REASON_FLAG = "--reason"
REASON_MODEL_FLAG = "--reason-model"


def launch(store: Store, *, trigger_source: str = "hook") -> dreaming.ClaimResult:
    """Claim with the configured Manage reasoner and launch its one-shot worker."""
    reasoner_kind, host, model = _manage_target(store)
    result = dreaming.claim_due(
        store,
        host or reasoner_kind,
        trigger_source=trigger_source,
        reasoner=reasoner_kind,
        model=model,
    )
    if result.claim is None:
        return result
    claim = result.claim
    command = detached.installed(EXECUTABLE)
    environment = {**os.environ, STORE_ENV_VAR: str(store.root), EXECUTOR_ENV_VAR: "1"}
    try:
        store.layout.state_dir.mkdir(parents=True, exist_ok=True)
        with (store.layout.state_dir / LOG_FILENAME).open("a", encoding="utf-8") as log:
            worker = [command, COMMAND, CLAIM_FLAG, claim.id, REASON_FLAG, reasoner_kind]
            if reasoner_kind == REASONER_HOST:
                worker.extend((REASON_HOST_FLAG, host))
            if model:
                worker.extend((REASON_MODEL_FLAG, model))
            subprocess.Popen(
                worker,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                **detached.options(),
            )
    except OSError as error:
        dreaming.mark_failed(store, claim.id, f"worker launch failed: {error}")
        return dreaming.ClaimResult(
            None,
            "worker launch failed",
            result.sessions_since,
            due=result.due,
        )
    return result


def run_due(
    store: Store,
    reasoner: Reasoner | None,
    *,
    reasoner_kind: str,
    host: str = "",
    model: str = "",
    trigger_source: str,
) -> dict[str, object]:
    """Run the same claimed Manage pipeline used by a detached Hook worker."""
    target = host if reasoner_kind == REASONER_HOST else reasoner_kind
    result = dreaming.claim_due(
        store,
        target,
        trigger_source=trigger_source,
        reasoner=reasoner_kind,
        model=model,
    )
    diagnostic = _reasoner_diagnostic(reasoner_kind, host, model)
    if result.claim is None:
        return {
            "slept": False,
            "status": "skipped",
            "trigger_source": trigger_source,
            "due": result.due,
            "reason": result.reason,
            "sessions_since": result.sessions_since,
            "reasoner": diagnostic,
        }
    report = run_worker(store, result.claim.id, reasoner)
    return {
        "slept": bool(report.get("dreamed")),
        "status": "succeeded" if report.get("dreamed") else "skipped",
        "trigger_source": trigger_source,
        "due": result.due,
        "sessions_since": result.sessions_since,
        "reasoner": diagnostic,
        **report,
    }


def run_worker(store: Store, claim_id: str, reasoner: Reasoner | None) -> dict[str, object]:
    """Run exactly one claimed Dream and exit. The report is the completion fence."""
    try:
        with file_lock(
            store.layout.dream_run_lock,
            timeout=store.config.storage.lock_timeout_seconds,
        ):
            claim = dreaming.current_claim(store, claim_id)
            if claim is None:
                status = dreaming.state(store)
                return {
                    "dreamed": status.get("status") == dreaming.STATUS_SUCCEEDED,
                    "claim": claim_id,
                    "reason": "claim already completed or superseded",
                }
            with file_lock(store.layout.maintenance_lock, timeout=None):
                claim = dreaming.current_claim(store, claim_id)
                if claim is None:
                    return {"dreamed": False, "claim": claim_id, "reason": "claim superseded"}
                report = Manage(store).sleep(reasoner=reasoner, dream_id=claim.id)
            dreaming.mark_succeeded(store, claim, report.path)
            return {
                "dreamed": True,
                "claim": claim.id,
                "trigger_source": claim.trigger_source,
                "reasoner": _reasoner_diagnostic(
                    claim.reasoner,
                    claim.host if claim.reasoner == REASONER_HOST else "",
                    claim.model,
                ),
                **report.as_dict(),
            }
    except LockTimeoutError:
        return {
            "dreamed": False,
            "claim": claim_id,
            "reason": "another dream worker still owns the run lock",
        }
    except Exception as error:
        dreaming.mark_failed(store, claim_id, f"{type(error).__name__}: {error}")
        raise


def _manage_target(store: Store) -> tuple[str, str, str]:
    """Resolve the configured Manage target without borrowing the Write source Host."""
    executor = store.config.executor
    manage = executor.manage
    reasoner = manage.reasoner or executor.reasoner
    if reasoner == REASONER_HOST:
        return reasoner, manage.host or executor.host, manage.host_model or executor.host_model
    if reasoner == REASONER_ENDPOINT:
        return reasoner, "", manage.model or executor.model
    return reasoner, "", ""


def _reasoner_diagnostic(kind: str, host: str, model: str) -> dict[str, str]:
    payload = {"kind": kind}
    if kind == REASONER_HOST and host:
        payload["host"] = host
    if model:
        payload["model"] = model
    return payload
