# Testing scope (firm rule)

Only database-layer functions get automated tests — never Discord-facing cog
classes/command handlers. Confirmed in `tests/test_db_methods.py`, the only test
file in the repo: it tests `database.db_methods.register_user` and
`cogs/user_goals/goal_db_methods.py`'s goal functions (`add_goal`, and the
`ordered_goals` view behavior via `get_goals`). Note the second one lives inside a
`cogs/` folder but is still pure DB code with no `discord`/`commands.Cog` import —
that's exactly why it's tested despite its location; the rule is about what the code
touches, not which folder it's in. No cog class (`User_Goals`, `Wise_Old_Man`,
`Runescape_Logger`) has any test coverage, and none is expected to.

This is a stated repo policy (confirmed directly by the repo owner), not just an
inferred pattern from what happens to exist today — don't propose adding tests for
cog/command code, and don't treat a cog's lack of tests as a gap to flag in review.

Test mechanics: `pytest`, fixtures for connection (`test_db`, module-scoped) and
table setup (function-scoped, drop-and-recreate from the real schema each run),
plain `assert` statements, no mocking framework — tests hit a real `Discord_Test`
MySQL database via `~/.my.cnf`, not an in-memory or mocked DB
(tests/test_db_methods.py:17-30).
