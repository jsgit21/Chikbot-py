-- Backfill the audit table on schemas that predate it.
--
-- audit has been in SCHEMA.sql without a migration ever creating it; candyland
-- already has it (created out-of-band before the migration process existed),
-- but candyland_test does not. This brings both in line with SCHEMA.sql.
--
-- Run against BOTH schemas, e.g.:
--   mysql candyland      < 2026-09-13_backfill_audit_table.sql
--   mysql candyland_test < 2026-09-13_backfill_audit_table.sql
--
-- IF NOT EXISTS makes this a no-op against candyland; only candyland_test
-- actually creates the table.

create table if not exists audit (
  id int unsigned not null auto_increment,
  actor_user_id bigint unsigned default null,
  action varchar(64) not null,
  payload json default null,
  created_at timestamp null default current_timestamp,
  primary key (id)
) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci;
