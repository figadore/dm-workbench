# Dungeon Output Refresh — Superseded Reference

Output quality is part of the unified one-shot roadmap, not paused behind the old P7-14 gate.

The [implementation plan](dm-assistant-implementation-plan.md) assigns the retained outcomes:

- **P7-16 — Prompt to Play:** normal browser sign-in, visual shell, inline map/guide review, manual
  editing, and purpose-based exports instead of a file/JSON dump.
- **P7-17 — Maps Worth Exploring:** compact geometry, real terrain, intentional styling, and useful
  map/component interaction.
- **P7-18 — Revise with Your Assistant:** visibly scoped conversations and human-accepted edits.
- **P7-20 — Print at the Table:** separately gated reference/tactical output with page/coverage limits,
  exact scale, calibration, registration and nonblank-page validation. Print stays disabled until proven.

[Architecture §§13 and 15](dm-assistant-technical-architecture.md#13-dungeon-generation) define output
and UI boundaries. Player filtering precedes rendering; cosmetic improvement never changes geometry
or grants access to secrets. Git preserves the original defects and P7-13e–g task text.

Only [project status](PROJECT_STATUS.md) selects a live task. This file is a navigation stub, not a
second implementation plan.
