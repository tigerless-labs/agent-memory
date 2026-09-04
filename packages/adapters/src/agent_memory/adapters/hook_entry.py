"""Hook entry point. It captures and triggers; it decides nothing and it never fails loudly.

A hook that breaks its host is worse than a hook that never fires, so every path here ends
in exit code 0 and any trouble goes to the store's own log.
"""

from __future__ import annotations

import json
import pathlib
import shlex
import signal
import subprocess
import sys
import traceback
from collections.abc import Callable, Sequence
from types import FrameType

from agent_memory.core import injection
from agent_memory.core.store import Store

from . import capture as capture_module
from . import moments, transcript

EXIT_OK = 0
LOG_FILENAME = "hooks.log"
KEY_SESSION = "session_id"
KEY_TRANSCRIPT = "transcript_path"
KEY_EVENT_CLAUDE = "hook_event_name"
KEY_EVENT_GENERIC = "event"
KEY_HOST = "host"
KEY_ITEMS = "items"
CLAUDE_OUTPUT_KEY = "hookSpecificOutput"
CLAUDE_CONTEXT_KEY = "additionalContext"
KEY_DISTILL = "distill"
DISTILL_LAUNCHED = "launched"
DISTILL_SKIPPED = "skipped"
SESSION_FLAG = "--session"
STORE_FLAG = "--store"

Launcher = Callable[[Store, str], bool]


class _Timeout(Exception):
    pass


def main(argv: Sequence[str] | None = None) -> int:
    store: Store | None = None
    try:
        event = json.loads(sys.stdin.read() or "{}")
        store = Store(event.get("store"), agent=str(event.get("agent") or "hook"))
        _arm(store.config.write.hook_timeout_seconds)
        response = handle(store, event)
        if response:
            print(json.dumps(response))
    except Exception:
        _log(store, traceback.format_exc())
    finally:
        _disarm()
    return EXIT_OK


def handle(
    store: Store, event: dict[str, object], launch: Launcher | None = None
) -> dict[str, object]:
    host = str(event.get(KEY_HOST) or moments.HOST_CLAUDE_CODE)
    raw_event = str(event.get(KEY_EVENT_CLAUDE) or event.get(KEY_EVENT_GENERIC) or "")
    moment = moments.moment_for(host, raw_event)
    if moment == moments.MOMENT_INJECT:
        return _inject(store, host)
    if moment in (moments.MOMENT_PAUSE, moments.MOMENT_EVICT):
        return _boundary(store, event, moment, launch or launch_distill)
    return {}


def _inject(store: Store, host: str) -> dict[str, object]:
    context = injection.payload(store)
    if not context:
        return {}
    if host == moments.HOST_CLAUDE_CODE:
        return {
            CLAUDE_OUTPUT_KEY: {
                KEY_EVENT_CLAUDE: "SessionStart",
                CLAUDE_CONTEXT_KEY: context,
            }
        }
    return {CLAUDE_CONTEXT_KEY: context}


def _boundary(
    store: Store, event: dict[str, object], moment: str, launch: Launcher
) -> dict[str, object]:
    session = str(event.get(KEY_SESSION) or "")
    if not session:
        return {}
    items = _items(event)
    result = capture_module.capture(store, session, items, source=moment)
    if result.is_empty():
        return {}
    launched = store.config.write.distill_on_boundary and launch(store, session)
    return {
        "moment": moment,
        "session": session,
        "pending": len(result.increment),
        "archived": result.archived,
        "pointer": result.pointer,
        KEY_DISTILL: DISTILL_LAUNCHED if launched else DISTILL_SKIPPED,
    }


def launch_distill(store: Store, session: str) -> bool:
    """The executor runs in its own process so the host's turn ends without waiting on it."""
    command = shlex.split(store.config.executor.command)
    if not command:
        return False
    try:
        subprocess.Popen(
            [*command, STORE_FLAG, str(store.root), SESSION_FLAG, session],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True


def _items(event: dict[str, object]) -> list[str]:
    supplied = event.get(KEY_ITEMS)
    if isinstance(supplied, list):
        return [str(item) for item in supplied]
    path = event.get(KEY_TRANSCRIPT)
    return transcript.items(pathlib.Path(str(path))) if path else []


def _arm(seconds: float) -> None:
    def _raise(signum: int, frame: FrameType | None) -> None:
        raise _Timeout()

    signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, seconds)


def _disarm() -> None:
    signal.setitimer(signal.ITIMER_REAL, 0)


def _log(store: Store | None, message: str) -> None:
    if store is None:
        return
    try:
        store.layout.state_dir.mkdir(parents=True, exist_ok=True)
        with (store.layout.state_dir / LOG_FILENAME).open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except OSError:
        return


if __name__ == "__main__":
    raise SystemExit(main())
