# Chikbot-py
Personal discord bot using the Py-cord library

## CI

`.github/workflows/ci.yml` runs on every pull request and on pushes to `main`.
It covers the Candyland pure-logic tests (`tests/test_candyland_roll.py`), which
need no database. The DB-backed tests are not in CI yet; they need a MySQL
service container, which follows separately.
