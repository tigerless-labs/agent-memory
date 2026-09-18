# Premise-aware adaptive read

The host assesses whether answering plausibly requires prior personal, project, or session
state. Self-contained tasks retain the ordinary answer path. For memory-dependent tasks the
host searches, selectively reads full entries, and checks support for the precise requested
facts and relationships. Partial evidence warrants one focused search for the missing facts;
unresolved specifics remain explicitly unknown. Search and full reads have fixed budgets.

The shared prompt module owns this policy for the native agentic exam and generated skill.
RecallConfig's master switch disables both adaptive guidance and the earlier evidence gate,
recovering the mainline exam policy for paired comparisons. Configuration fingerprints record
the switch and budgets. Fixed exams retain their existing separate framing.

This is host guidance, not an enforced runtime controller or model judge. Passive observation
records command rounds and results without modifying retrieval. Retrieval ranking, write,
manage, lifecycle and raw storage retain their behavior. Tests prove delivery and ablation;
answer quality requires paired replays at one revision over indexed copies of identical truth.
