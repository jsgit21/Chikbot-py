-- Team custom emoji.
--
-- Adds team.emoji_id: the Discord numeric ID of that team's custom server
-- emoji, captured once at team creation time. Only /candyland setup-gmers-land's
-- three preset teams populate it (an acronym-matched custom emoji uploaded ahead
-- of the event); /candyland team-add leaves it NULL. Emoji markup is fetched on
-- demand at roll time via bot.get_emoji(id) and bot.fetch_emoji(id), with
-- fallback to the dice emoji if the emoji no longer exists.
--
-- Run against BOTH schemas:
--   mysql candyland      < 2026-09-12_team_emoji.sql
--   mysql candyland_test < 2026-09-12_team_emoji.sql
--
-- No preconditions.

alter table team add column emoji_id bigint unsigned null after acronym;
