# Config & secrets

- All secrets/config come from environment variables via `python-dotenv` +
  `os.getenv(...)`, loaded with `load_dotenv()` near the top of whichever
  module needs it (chikbot.py:6,9; cogs/wise_old_man/wom_utilities.py:3,5 — note
  it's called again independently there rather than relying on chikbot.py's earlier
  call, since that module can also run standalone via its `if __name__ == '__main__'`
  block at wom_utilities.py:172-177).
- `.env.example` at repo root documents every expected var with a comment header per
  group (Dink channels, Dink webhooks, Dink FWD webhooks, WOM config) — add new vars
  there when adding new ones to code.
- Discord snowflake IDs are always cast with `int(os.getenv('X'))` right at read
  time, never left as strings: chikbot.py:11-13, runescape_logger.py:13-14,
  wise_old_man.py:15-16.
- No `.env` file or secrets are committed (`.gitignore:105`).
