-- Task schema (Majors + Minors) and the whole-event Minor exclusion history.
--
-- Adds candyland.task (one row per Major or Minor, kind discriminator),
-- candyland.team_minor_history (every Minor a team has ever drawn - the
-- never-repeat guard and the reporting log), and tile_thread.minor_task_id
-- (which Minor a tile's thread showed - needed both to render it and as the
-- exclusion source-of-truth alongside team_minor_history).
--
-- Run against BOTH schemas, e.g.:
--   mysql candyland      < 2026-09-15_task_and_minor_history.sql
--   mysql candyland_test < 2026-09-15_task_and_minor_history.sql
--
-- No preconditions. Seeds no rows - Nick's real tile/Minor spreadsheet lands
-- in a follow-up seed script once the tile grammar is locked.

create table task (
  id int unsigned primary key auto_increment,
  kind enum('major','minor') not null,
  tile_sequence int null,
  title varchar(255) not null,
  task varchar(1000) not null,
  notes varchar(1000) null,
  unique key uq_task_tile_sequence (tile_sequence)
);

create table team_minor_history (
  id int unsigned primary key auto_increment,
  team_id int unsigned not null,
  minor_task_id int unsigned not null,
  tile_thread_id int unsigned not null,
  assigned_at datetime not null default current_timestamp,
  unique key uq_team_minor (team_id, minor_task_id),
  foreign key (team_id) references team(id),
  foreign key (minor_task_id) references task(id),
  foreign key (tile_thread_id) references tile_thread(id)
);

alter table tile_thread
  add column minor_task_id int unsigned null,
  add constraint fk_tile_thread_minor foreign key (minor_task_id) references task(id);
