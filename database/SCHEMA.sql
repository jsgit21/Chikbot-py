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
  board_slug varchar(32) not null,          -- 'standard' now, 'hard' after reveal
  status enum('setup','live','ended') not null default 'setup',
  starts_at datetime,
  ends_at datetime,
  created_at timestamp default current_timestamp
);

create table candyland.team (
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

create table candyland.tile_thread (
  id int unsigned primary key auto_increment,
  team_id int unsigned not null,
  board_slug varchar(32) not null,
  tile_sequence int not null,
  thread_id bigint unsigned not null,       -- the Discord forum post/thread
  state enum('open','closed') not null default 'open',
  opened_at timestamp default current_timestamp,
  closed_at timestamp null,
  constraint fk_thread_team foreign key (team_id)
    references team (id) on delete cascade,
  unique key (team_id, board_slug, tile_sequence)
);
-- At most one open thread per team is a runtime invariant enforced in code,
-- not a DB constraint (MySQL cannot do a partial unique index).

create table candyland.movement (
  id int unsigned primary key auto_increment,
  team_id int unsigned not null,
  kind enum('roll','adjustment','board_transition') not null,
  board_slug varchar(32) not null,
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
-- APPEND ONLY. Never update or delete a row. Corrections are a new
-- 'adjustment' row.

create table candyland.team_state (
  team_id int unsigned primary key,
  board_slug varchar(32) not null,
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
  board_slug varchar(32) not null,
  bounty_key varchar(16) not null,          -- 'A'..'D','BOOST','UNDERSTUDY','SWAP'
  used_on_sequence int not null,
  movement_id int unsigned,
  created_at timestamp default current_timestamp,
  constraint fk_bounty_team foreign key (team_id)
    references team (id) on delete cascade,
  unique key (team_id, board_slug, bounty_key)
);

create table candyland.audit (
  id int unsigned primary key auto_increment,
  actor_user_id bigint unsigned,
  action varchar(64) not null,
  payload json,
  created_at timestamp default current_timestamp
);

-- tile: deferred to Phase F (board content + images)
