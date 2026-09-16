create table Discord.user (
  user_id bigint unsigned primary key,
  username varchar(32) not null,
  first_seen timestamp default current_timestamp
);

create table Discord.user_alias (
  user_id bigint unsigned primary key,
  alias varchar(32),
  unique key (user_id, alias)
);

create table Discord.user_goal (
  id int primary key auto_increment,
  user_id bigint unsigned,
  goal varchar(255),
  completed boolean default false,
  insert_date timestamp default current_timestamp,
  completed_date timestamp,
  constraint fk_parent_id foreign key (parent_id) references user_goal (id) on delete cascade
);

create view Discord.ordered_goals as (
  select g.*,
       (g.id <> g.parent_id) as sub_goal,
       coalesce(s.insert_date, g.insert_date) as parent_insert_date,
       row_number() over (
          partition by g.user_id
          order by coalesce(s.insert_date, g.insert_date), (g.id <> g.parent_id), g.id
       ) as rnk
    from Discord.user_goal g
    left join Discord.user_goal s
      on g.parent_id = s.id
);

create table candyland.event (
  id int unsigned primary key auto_increment,
  slug varchar(64) not null unique,
  board2_revealed_at datetime null,         -- set by /candyland doomsday (Phase C) to unhide Board 2
  status enum('setup','live','ended') not null default 'setup',
  starts_at datetime,
  ends_at datetime,
  created_at timestamp default current_timestamp
);

create table candyland.team (
  id int unsigned primary key auto_increment,
  event_id int unsigned not null,
  name varchar(64) not null,
  acronym varchar(16) null,                 -- short tag; render falls back to name when null
  emoji_id bigint unsigned null,            -- this team's custom-emoji id; null unless set by setup-gmers-land
  role_id bigint unsigned not null,         -- the Discord role that authorises /candyland roll
  forum_channel_id bigint unsigned not null,-- where this team's per-tile threads are created
  voice_channel_id bigint unsigned null,    -- open team voice channel; null for teams created before this column existed
  chat_channel_id bigint unsigned null,     -- private team text channel; null for teams created before this column existed
  sort_order int not null default 0,
  created_at timestamp default current_timestamp,
  constraint fk_team_event foreign key (event_id)
    references event (id) on delete cascade,
  unique key (event_id, role_id)
);

create table candyland.task (
  id int unsigned primary key auto_increment,
  kind enum('major','minor') not null,
  tile_sequence int null,                   -- populated only for kind='major'
  title varchar(255) not null,
  task varchar(1000) not null,
  notes varchar(1000) null,
  unique key uq_task_tile_sequence (tile_sequence)
);
-- One row per Major or Minor, Phase F (schema landed 2026-09-15, real data a
-- follow-up seed script once Nick's tile/Minor spreadsheet is locked).
-- uq_task_tile_sequence is the DB-level guarantee of one tile per Major.

create table candyland.tile_thread (
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
-- At most one open thread per team is a runtime invariant enforced in code,
-- not a DB constraint (MySQL cannot do a partial unique index). Which
-- Minor(s) this thread showed is not a column here - it is derived by
-- querying team_minor_history for this row's id, since a tile can carry more
-- than one Minor (2 past the doomsday tile, decision 43) and a fixed column
-- count would not generalise.

create table candyland.team_minor_history (
  id int unsigned primary key auto_increment,
  team_id int unsigned not null,
  minor_task_id int unsigned not null,
  tile_thread_id int unsigned not null,
  assigned_at datetime not null default current_timestamp,
  unique key uq_team_minor (team_id, minor_task_id),
  foreign key (team_id) references team (id),
  foreign key (minor_task_id) references task (id),
  foreign key (tile_thread_id) references tile_thread (id)
);
-- Every Minor a team has ever drawn, whole event (decision 39's amended
-- exclusion rule: never the same Minor twice, not just not-in-a-row) - one
-- row per Minor, so a two-Minor tile (decision 43) writes two rows sharing
-- the same tile_thread_id. Doubles as the post-event reporting log and as the
-- lookup for which Minor(s) a given tile_thread showed. uq_team_minor is the
-- DB-level guarantee; the Python exclusion logic in draw_minors is the
-- primary mechanism.

create table candyland.movement (
  id int unsigned primary key auto_increment,
  team_id int unsigned not null,
  -- 'catchup_roll' is a roll. If you add another kind that represents a completed
  -- roll, update get_pending_modifier AND get_last_bounty_since_roll, which both
  -- anchor on "the team's last roll".
  kind enum('roll','adjustment','board_transition','catchup_roll') not null,
  roll_total tinyint unsigned,              -- roll result, 2..5 normally, up to 20 with a Double Down bounty plus the doomsday catch-up die; null for adjustment/board_transition. start/end are from_sequence/to_sequence
  from_sequence int not null,
  to_sequence int not null,
  proof_thread_id bigint unsigned,          -- the thread whose images justified this move
  invoked_by_user_id bigint unsigned,       -- who ran the command
  note varchar(255),
  created_at timestamp default current_timestamp,
  constraint fk_movement_team foreign key (team_id)
    references team (id) on delete cascade
);
-- APPEND ONLY. Never update or delete a row. Corrections are a new
-- 'adjustment' row.

create table candyland.team_state (
  team_id int unsigned primary key,
  current_sequence int not null default 1,
  last_movement_id int unsigned,
  updated_at timestamp default current_timestamp on update current_timestamp,
  constraint fk_state_team foreign key (team_id)
    references team (id) on delete cascade
);
-- DERIVED. Written only by the fold in candyland_db_methods. movement is the
-- source of truth; this is a cache for cheap reads by chikbot and the website.

create table candyland.bounty_use (
  id int unsigned primary key auto_increment,
  team_id int unsigned not null,
  board_number tinyint unsigned not null,   -- which board the used-on tile is on, at write time; "each bounty once per board"
  bounty_key varchar(16) not null,          -- RETREAT, ADVANCE, CHARGE, DISADVANTAGE, ADVANTAGE, DOUBLE_DOWN, SWAP
  used_on_sequence int not null,
  movement_id int unsigned,
  claimed_at datetime null,                 -- null: taken but not completed; this is what "outstanding" means
  created_at timestamp default current_timestamp,
  constraint fk_bounty_team foreign key (team_id)
    references team (id) on delete cascade,
  unique key (team_id, board_number, bounty_key)
);

create table candyland.bounty (
  id tinyint unsigned primary key auto_increment,
  board_number tinyint unsigned not null,
  bounty_key varchar(16) not null,          -- RETREAT, ADVANCE, CHARGE, DISADVANTAGE, ADVANTAGE, DOUBLE_DOWN, SWAP
  task varchar(255) not null,               -- phrased to follow "This means that "
  reward varchar(500) not null,             -- phrased to follow "your team will:"
  unique key (board_number, bounty_key)
);

create table candyland.audit (
  id int unsigned primary key auto_increment,
  actor_user_id bigint unsigned,
  action varchar(64) not null,
  payload json,
  created_at timestamp default current_timestamp
);

-- tile: deferred to Phase F (board content + images)
