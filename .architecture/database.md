# Database access

## Where it lives
Plain functions in a module, not a class or ORM. Two such modules exist:
`database/db_methods.py` (repo-wide: users, WOM group sync, Dink transaction
tracking) and `cogs/user_goals/goal_db_methods.py` (goals feature only — imports
`database.db_methods` just for its connection helper, goal_db_methods.py:2).
Feature-specific DB logic living inside the feature's own cog folder is only one data
point (the goals feature) — don't assume every future feature's DB code belongs in
its own cog folder without checking whether it needs to be shared elsewhere first.

## Connection pattern
Every function opens its own connection via `create_connection()`
(database/db_methods.py:3-10 — `pymysql.connect(..., read_default_file='~/.my.cnf',
autocommit=True)`) unless a `testdb` object is passed in. No shared/pooled
connection, no context manager, no explicit `.close()` in the normal (non-test) path.

## Test injection
Functions that have real test coverage take an optional trailing `testdb=None` kwarg:
`db = testdb if testdb else create_connection()` (db_methods.py:12-13, and all five
functions in goal_db_methods.py). This is how `tests/test_db_methods.py` injects a
connection to a separate `Discord_Test` database instead of touching prod data. Not
applied uniformly: `update_local_wom_group`, `check_local_wom`,
`register_latest_dink_transaction`, `get_latest_dink_transaction` in db_methods.py
have no `testdb` param and aren't unit tested — the param only shows up on functions
someone actually wrote a test for, it isn't a blanket rule to add to every DB
function on principle.

## Calling DB code from async Discord handlers
Sync pymysql calls get wrapped in `await asyncio.to_thread(...)` before being awaited
from a cog command or event handler — this is the dominant pattern: chikbot.py:60
(`on_message`), and every slash-command handler in `user_goals.py` (11 call sites,
e.g. user_goals.py:51, 63, 71, 80, 89, 102, 113, 130, 144, 160, 176).

**Exception, worth knowing about**: `wise_old_man.py` does not follow this. Its
`sync_wom_whitelist` command calls `database.update_local_wom_group(...)` directly
and un-wrapped (wise_old_man.py:32), and the `update_wom_group`/`rolecheck` task
loops do the same via `sync_wom_group_to_db()` and `get_misranked_users()`
(wise_old_man.py:111-127, 136-161) — blocking calls to the DB and the WOM HTTP API run
straight on the event loop. This is an existing inconsistency, not a second valid
pattern to copy. New async command/task code that hits the DB should follow the
`asyncio.to_thread` pattern from `user_goals.py`, not `wise_old_man.py`.

## Schema
`database/SCHEMA.sql` is the source of truth for table/view DDL (`user`,
`user_alias`, `user_goal`, the `ordered_goals` view). Tests recreate structures in a
separate `Discord_Test` database using `show create table`/`show create view`
against the real `Discord` schema rather than re-declaring DDL by hand
(tests/test_db_methods.py:70-80) — keeps the test schema from drifting out of sync
with SCHEMA.sql.
