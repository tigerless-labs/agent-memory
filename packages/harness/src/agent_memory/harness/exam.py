"""Two ways to sit the exam.

The agentic exam lets the host drive its own retrieval, which is how the system is really
used — and which makes the host's search behaviour part of every measurement. Repeated
replays of one frozen configuration moved by +/-7 answers per 120 episodes, enough to bury
any difference between memory configurations.

The fixed exam removes that degree of freedom: the harness performs the recall itself, builds
one context from the result, and asks a single question with no tools. What varies is then one
generation instead of an agent loop, which is what makes memory configurations comparable.
"""

from __future__ import annotations

from agent_memory.core import context as core_context
from agent_memory.core.store import Store

MODE_AGENTIC = "agentic"
MODE_FIXED = "fixed"
MODES = (MODE_AGENTIC, MODE_FIXED)

ENTRY_SEPARATOR = "\n\n"
CONTEXT_HEADER = "Entries from your memory store, most relevant first:"
NOTHING_FOUND = "Your memory store returned nothing for this question."
CONTEXT_PLACEHOLDER = "<<retrieved-context>>"


def build_context(store: Store, question: str, full_text_entries: int) -> core_context.Context:
    """Delegates to the core read surface; the harness holds no retrieval policy of its own."""
    store.config.recall.context_full_text_entries = full_text_entries
    return core_context.build(store, question, deep=store.config.recall.raw_enabled)


def fill_context(prompt: str, context: str) -> str:
    return prompt.replace(CONTEXT_PLACEHOLDER, context)
