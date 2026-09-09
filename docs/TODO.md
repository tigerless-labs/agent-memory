# Follow-ups

- Decide explicit confirmation and host-level authorization for permanent GC, import and
  cross-store changes; CLI labels alone do not identify a human.
- Decide preimage retention and recovery guarantees for split and in-place correction,
  including stores outside Git and multi-file Manage failures.
- Decide whether direct link/unlink delta commands, relation audit history and per-operation
  bounds are needed; current correct replaces the complete list.
- Decide if explicit deep Raw search should suppress evidence cited exclusively by invalid
  memories; shared evidence and historical queries must remain available.
- Correct explicit feedback persistence: Store.feedback currently returns an adjusted object
  without writing the weight back to disk.
