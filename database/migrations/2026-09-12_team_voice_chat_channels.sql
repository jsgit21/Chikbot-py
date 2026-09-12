-- Team voice + chat channels.
--
-- Adds team.voice_channel_id and team.chat_channel_id so /candyland team-add can
-- provision a voice channel and a private text channel alongside the existing
-- forum, growing a team's Discord footprint from 1 role + 1 forum to 1 role +
-- 3 channels. Both columns are nullable, mirroring the team.acronym precedent
-- (2026-09-04_bounty_claim_flow.sql): every team row registered from here on
-- always populates both ids, but existing team rows (registered before this
-- migration) are left NULL and stay valid with no backfill. Downstream code
-- (delete/teardown) tolerates a null id the same way it already tolerates a
-- null role_id.
--
-- Run against BOTH schemas:
--   mysql candyland      < 2026-09-12_team_voice_chat_channels.sql
--   mysql candyland_test < 2026-09-12_team_voice_chat_channels.sql
--
-- No preconditions.

alter table team add column voice_channel_id bigint unsigned null after forum_channel_id;
alter table team add column chat_channel_id bigint unsigned null after voice_channel_id;
