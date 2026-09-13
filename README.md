# Chikbot-py
Personal discord bot using the Py-cord library

## CI

`.github/workflows/ci.yml` runs on every pull request and on pushes to `main`.
It covers the Candyland pure-logic tests (`tests/test_candyland_roll.py`), which
need no database. The DB-backed tests are not in CI yet; they need a MySQL
service container, which follows separately.

## Deploying

chikbot runs as a systemd service from `/opt/chikbot` on `jsvps`. To ship `main`,
SSH in and run `./deploy.sh` from that directory.

The script refuses to run on a dirty tree or on any branch but `main`, skips the
restart when there is nothing new to pull, reinstalls dependencies only when
`requirements.txt` changed, and fails the deploy if the bot is not healthy five
seconds after the restart.
