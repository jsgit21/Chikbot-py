-- Team custom emoji.
--
-- Adds team.emoji: the ready-to-use Discord markup for that team's custom
-- server emoji (e.g. <:BBC:1234567890123456>), captured once at team
-- creation time instead of re-resolved by name on every message - stays
-- correct even if the emoji is later renamed, and costs no extra Discord API
-- call in the roll hot path. Only /candyland setup-gmers-land's three preset
-- teams populate it (an acronym-matched custom emoji uploaded ahead of the
-- event); /candyland team-add leaves it NULL, same nullable-column precedent
-- as voice_channel_id / chat_channel_id (2026-09-12_team_voice_chat_channels.sql).
-- Downstream code falls back to the dice emoji when null.
--
-- Run against BOTH schemas:
--   mysql candyland      < 2026-09-12_team_emoji.sql
--   mysql candyland_test < 2026-09-12_team_emoji.sql
--
-- No preconditions.

alter table team add column emoji varchar(64) null after acronym;
