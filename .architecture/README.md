# Architecture notes

Reference docs on established coding patterns in Chikbot-py, grounded in what the code
actually does, not aspirational style guides. Written for quick lookup, not tutorials.
Snapshot as of `main` @ c4dd473.

- [cogs.md](cogs.md) — cog structure, registration, naming, commands, task loops
- [database.md](database.md) — db access pattern, test injection, sync/async boundary
- [testing.md](testing.md) — what gets automated tests and what doesn't (firm rule)
- [config.md](config.md) — env vars, secrets, ID typing
- [open-questions.md](open-questions.md) — things that look like conventions but aren't settled yet

No linter/formatter config exists in this repo (no `pyproject.toml`, `setup.cfg`,
`.flake8`, ruff config) — style notes here are observed practice, not tool-enforced.
Each entry cites the file/line it was verified against; if code has moved on, trust
the code over this doc and update the doc.
