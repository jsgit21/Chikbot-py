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
