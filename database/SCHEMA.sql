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

-- One Discord user can own many RSNs (one-to-many). Keyed by wom_user_id, the
-- stable WOM player id, so the link survives in-game renames (a rename is an
-- UPDATE on wom_group, not a delete). The current RSN is never stored here; it
-- is always read from wom_group, which the daily sync keeps up to date.
--
-- The FK to wom_group keeps the two tables from drifting. ON DELETE CASCADE is
-- required because the daily sync (update_local_wom_group) deletes members who
-- leave the group: cascade removes their link with them (re-link via /wom link
-- on rejoin). RESTRICT would instead make that sync delete fail.
create table Discord.wom_link (
  wom_user_id int unsigned primary key,
  user_id bigint unsigned not null,
  linked_at timestamp default current_timestamp,
  constraint fk_wom_link_user foreign key (user_id) references Discord.user (user_id),
  constraint fk_wom_link_group foreign key (wom_user_id) references Discord.wom_group (wom_user_id) on delete cascade
);

-- Conversational alias used in competition titles/posts ("mayo", "peppy").
alter table Discord.user add column preferred_alias varchar(32) null;

-- A BOTW + SOTW pairing and its lifecycle. Drives "weeks since last cycle".
create table Discord.competition_cycle (
  id int unsigned primary key auto_increment,
  starts_at datetime not null,
  ends_at datetime not null,
  status enum('planned', 'publishing', 'active', 'ended') default 'planned',
  created_at timestamp default current_timestamp
);

-- One row per WOM competition we create/track (two per cycle). Everything
-- WOM's API already returns (type, metric, title, dates, winner) is queried
-- live instead of mirrored here; this table only holds what has no WOM
-- equivalent. verification_code is sensitive: it grants edit/delete on the
-- WOM competition.
create table Discord.competition (
  competition_id int unsigned primary key,
  cycle_id int unsigned null,
  verification_code varchar(64) null,
  nominator_user_id bigint unsigned null,
  results_status enum('pending', 'drafted', 'announcing', 'announced', 'deferred') default 'pending',
  -- Only set for a standalone (solo) competition, tracking its kickoff-approval state.
  -- Paired (OTW) competitions track this via competition_cycle.status instead, so
  -- this stays null for them.
  kickoff_status enum('drafted', 'announced') null,
  created_at timestamp default current_timestamp,
  constraint fk_competition_cycle foreign key (cycle_id) references Discord.competition_cycle (id)
);
