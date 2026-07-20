# Open questions / not-yet-settled patterns

Things that look like they might be conventions but are only single data points,
contested, or actively unresolved as of this snapshot (`main` @ c4dd473). Don't cite
these as established without checking current state first.

## Where do cross-cutting constants live?
Today: a single flat `constants.py` at repo root, currently holding one value
(`EST = ZoneInfo('America/New_York')`, constants.py:3), imported directly
(`from constants import EST`, wise_old_man.py:8). There is no `shared/` package on
`main`.

Two open, unmerged PRs each independently invent a `shared/emojis.py` module for
unrelated emoji constants (GM_EMOJI in one, chicken/egg reaction emoji in the other)
— neither coordinated with the other, and neither considered just extending the
existing `constants.py`. Whichever merges second will hit an add/add git conflict on
that exact path. Before merging either, worth deciding: does `shared/` replace
`constants.py` going forward, do they coexist with a defined split (e.g.
`constants.py` for plain values, `shared/` for Discord objects like PartialEmoji), or
should the new emoji constants just go into `constants.py` instead? Not decided
anywhere in the codebase or its history — don't present either PR's choice as the
answer.

## Import ordering
Loose tendency toward stdlib → discord/third-party → local/relative, with
blank-line grouping in some files (user_goals.py, wise_old_man.py) but not others
(chikbot.py, runescape_logger.py list everything without grouping blanks). Not
consistent enough to call a rule; there's also no isort/ruff config to enforce one.

## Docstrings/comments
No module or function docstrings anywhere in the codebase except two inline test
docstrings (tests/test_db_methods.py:112-114, 166-172). Line comments (`#`) appear
sparingly and only to explain non-obvious *why* (e.g. db_methods.py:136 `# osrs
dedupes names regardless of hyphens`; goal_utilities.py:32 `# Ridiculous way I need
to add empty space for discord`) — never to restate what a line already says.
Consistent with what exists, but thin enough that it's more "absence of docstrings"
than a positive documented convention to point to.
