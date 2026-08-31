-- Board 2 continuation reshape. Run on candyland AND candyland_test.
-- All six tables are empty; this drops and recreates them from SCHEMA.sql.
set foreign_key_checks = 0;
drop table if exists bounty_use;
drop table if exists tile_thread;
drop table if exists movement;
drop table if exists team_state;
drop table if exists team;
drop table if exists event;
set foreign_key_checks = 1;

-- Then re-run the candyland.* CREATE TABLE statements from database/SCHEMA.sql
-- for: event, team, team_state, tile_thread, movement, bounty_use
-- (in that order - parent before child).
