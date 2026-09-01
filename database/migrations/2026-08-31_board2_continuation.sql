-- Board 2 continuation reshape.
--
-- Drops board_slug from movement/team_state/tile_thread, swaps
-- event.board_slug -> board2_revealed_at, bounty_use.board_slug -> board_number,
-- movement.dice_values -> roll_total, and rebuilds tile_thread's unique key as
-- (team_id, tile_sequence). All six candyland tables are empty (zero rows), so
-- this drops and recreates them from the current database/SCHEMA.sql rather than
-- issuing per-column ALTERs.
--
-- Run against BOTH schemas, e.g.:
--   mysql candyland      < 2026-08-31_board2_continuation.sql
--   mysql candyland_test < 2026-08-31_board2_continuation.sql
--
-- `audit` is unchanged and deliberately left alone.

set foreign_key_checks = 0;
drop table if exists bounty_use;
drop table if exists tile_thread;
drop table if exists movement;
drop table if exists team_state;
drop table if exists team;
drop table if exists event;
set foreign_key_checks = 1;

create table event (
  id int unsigned primary key auto_increment,
  slug varchar(64) not null unique,
  board2_revealed_at datetime null,         -- set by /candyland doomsday (Phase C) to unhide Board 2
  status enum('setup','live','ended') not null default 'setup',
  starts_at datetime,
  ends_at datetime,
  created_at timestamp default current_timestamp
);

create table team (
  id int unsigned primary key auto_increment,
  event_id int unsigned not null,
  name varchar(64) not null,
  role_id bigint unsigned not null,         -- the Discord role that authorises /candyland roll
  forum_channel_id bigint unsigned not null,-- where this team's per-tile threads are created
  sort_order int not null default 0,
  created_at timestamp default current_timestamp,
  constraint fk_team_event foreign key (event_id)
    references event (id) on delete cascade,
  unique key (event_id, role_id)
);

create table team_state (
  team_id int unsigned primary key,
  current_sequence int not null default 1,
  last_movement_id int unsigned,
  updated_at timestamp default current_timestamp on update current_timestamp,
  constraint fk_state_team foreign key (team_id)
    references team (id) on delete cascade
);

create table tile_thread (
  id int unsigned primary key auto_increment,
  team_id int unsigned not null,
  tile_sequence int not null,
  thread_id bigint unsigned not null,       -- the Discord forum post/thread
  state enum('open','closed') not null default 'open',
  opened_at timestamp default current_timestamp,
  closed_at timestamp null,
  constraint fk_thread_team foreign key (team_id)
    references team (id) on delete cascade,
  unique key (team_id, tile_sequence)
);

create table movement (
  id int unsigned primary key auto_increment,
  team_id int unsigned not null,
  kind enum('roll','adjustment','board_transition') not null,
  roll_total tinyint unsigned,              -- 1d4+1 result, 2..5; null for adjustment/board_transition. start/end are from_sequence/to_sequence
  from_sequence int not null,
  to_sequence int not null,
  proof_thread_id bigint unsigned,          -- the thread whose images justified this move
  invoked_by_user_id bigint unsigned,       -- who ran the command
  note varchar(255),
  created_at timestamp default current_timestamp,
  constraint fk_movement_team foreign key (team_id)
    references team (id) on delete cascade
);

create table bounty_use (
  id int unsigned primary key auto_increment,
  team_id int unsigned not null,
  board_number tinyint unsigned not null,   -- which board the used-on tile is on, at write time; "each bounty once per board"
  bounty_key varchar(16) not null,          -- 'A'..'D','BOOST','UNDERSTUDY','SWAP'
  used_on_sequence int not null,
  movement_id int unsigned,
  created_at timestamp default current_timestamp,
  constraint fk_bounty_team foreign key (team_id)
    references team (id) on delete cascade,
  unique key (team_id, board_number, bounty_key)
);
