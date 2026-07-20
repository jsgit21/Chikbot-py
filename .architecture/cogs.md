# Cogs

## Structure
- One cog per `cogs/<name>/` folder. The cog's own file matches the folder name
  exactly, no suffix: `cogs/runescape_logger/runescape_logger.py`,
  `cogs/user_goals/user_goals.py`, `cogs/wise_old_man/wise_old_man.py`. 3/3 merged
  cogs follow this.
- Cog-adjacent helper modules live as plain files in the same folder, not nested
  further: `goal_db_methods.py`, `goal_utilities.py` next to `user_goals.py`;
  `wom_utilities.py`, `rolecheck.py` next to `wise_old_man.py`. Imported with
  relative imports (`from . import goal_db_methods as database`,
  `from .rolecheck import ...`).

## Class naming
Cog classes use `PascalCase_With_Underscores` between words, not plain PascalCase:
`Runescape_Logger`, `User_Goals`, `Wise_Old_Man` (runescape_logger.py:7,
user_goals.py:14, wise_old_man.py:11). Consistent 3/3 — deliberate repo style, even
though it isn't PEP8 CapWords.

## Registration
- `chikbot.py` loads each cog synchronously, no `await`:
  `chikbot.load_extension('cogs.user_goals.user_goals')` etc. (chikbot.py:24-26).
- Every cog's `setup(bot)` calls `bot.add_cog(...)`, also no `await`
  (runescape_logger.py:90, user_goals.py:190, wise_old_man.py:165). This is correct
  for py-cord (requirements.txt:1) — py-cord kept these synchronous, unlike modern
  discord.py. Don't "fix" these by adding `await`.

## Commands
- Multi-subcommand cogs group under a `discord.SlashCommandGroup` class attribute,
  with `@goals.command(...)` on each method (user_goals.py:16, 23, 46, ...). Only one
  cog (`User_Goals`) currently needs this — reach for it once a cog has several
  related subcommands, not evidence every cog needs a group.
- Single standalone commands use `@discord.slash_command(...)` directly
  (wise_old_man.py:29). Only one example in the codebase.
- Role-gating a command: a plain function check (`is_moderator(ctx)`,
  wise_old_man.py:22-25) passed to `@commands.check(is_moderator)`, paired with a
  dedicated `@<command>.error` handler that special-cases
  `discord.errors.CheckFailure` and re-raises anything else as a bare `Exception`
  (wise_old_man.py:28-53). Only one command does this — it's the template to copy for
  a new moderator-only command, not a rule already applied elsewhere.

## Recurring/scheduled tasks
`@tasks.loop(time=datetime.time(hour=H, minute=M, tzinfo=EST))` on a cog method,
always paired with a `@<task>.before_loop` that does
`await self.bot.wait_until_ready()` first (wise_old_man.py:120-133, 135-160). `EST`
comes from `constants.py` (see open-questions.md for where shared constants live).
Two instances in the same cog, consistent with each other — follow this shape for any
new scheduled job.

## Error handling in cogs
Sparse, not a designed-in layer. Two data points, not a repo-wide pattern:
`rolecheck` wraps its full body in `try/except Exception`, prints, and reports
failure to the mod channel (wise_old_man.py:136-155); `sync_wom_whitelist_error` is
the one `@command.error` handler in the repo (wise_old_man.py:45-53). Most command
handlers (all of `user_goals.py`, all of `runescape_logger.py`) have no error
handling at all and will surface exceptions as py-cord's default per-listener logged
error rather than crashing the bot.
