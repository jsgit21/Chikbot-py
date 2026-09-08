-- Bounty claim flow + output polish.
--
-- Adds team.acronym, bounty_use.claimed_at, and the candyland.bounty text
-- table. Splits taking a bounty from claiming its reward: claimed_at null
-- means a team has taken the bounty but not yet completed it.
--
-- Run against BOTH schemas, e.g.:
--   mysql candyland      < 2026-09-04_bounty_claim_flow.sql
--   mysql candyland_test < 2026-09-04_bounty_claim_flow.sql
--
-- No preconditions. The bounty_use backfill is the only data touch: every row
-- taken before this migration is treated as already claimed (claimed_at =
-- created_at), so a bounty a team already completed under the old immediate-
-- reward flow does not read as outstanding and block that team from rolling.

alter table team add column acronym varchar(16) null after name;
alter table bounty_use add column claimed_at datetime null;

create table bounty (
  id tinyint unsigned primary key auto_increment,
  board_number tinyint unsigned not null,
  bounty_key varchar(16) not null,
  task varchar(255) not null,
  reward varchar(500) not null,
  unique key (board_number, bounty_key)
);

insert into bounty (board_number, bounty_key, task, reward) values
  (1, 'RETREAT',
   'your team must get 2 Glacial temotlis instead of this tile''s Major and Minor.',
   'move back 1 tile.'),
  (1, 'ADVANCE',
   'your team must get any 1, 2, or 3 Wilderness Wards instead of this tile''s Major and Minor.',
   'move forward 1 tile.'),
  (1, 'DISADVANTAGE',
   'your team must get a Willow composite bow instead of this tile''s Major and Minor.',
   'roll twice on your next roll and take the lower result.'),
  (1, 'ADVANTAGE',
   'your team must collect one Barrows piece per equipment slot, mixing brothers.',
   'roll twice on your next roll and take the higher result.'),
  (1, 'DOUBLE_DOWN',
   'your team must complete this tile a second time - Major and Minor again, fresh proof for both.',
   'roll two 1d4+1 and move the combined total (4-10). Overshooting still lands you on the final tile.'),
  (1, 'SWAP',
   'your team must redo any Major it has already cleared on this board.',
   'count this tile as complete and roll on.'),
  (2, 'RETREAT',
   'your team must get 2 Zulrah uniques instead of this tile''s Major and Minor.',
   'move back 1 tile.'),
  (2, 'ADVANCE',
   'your team must get the Beef pet instead of this tile''s Major and Minor.',
   'move forward 1 tile.'),
  (2, 'DISADVANTAGE',
   'your team must get a Yew composite bow instead of this tile''s Major and Minor.',
   'roll twice on your next roll and take the lower result.'),
  (2, 'ADVANTAGE',
   'your team must milk a Moon Man instead of this tile''s Major and Minor.',
   'roll twice on your next roll and take the higher result.'),
  (2, 'DOUBLE_DOWN',
   'your team must complete this tile a second time - Major and Minor again, fresh proof for both.',
   'roll two 1d4+1 and move the combined total (4-10). Overshooting still lands you on the final tile.'),
  (2, 'SWAP',
   'your team must redo any Major it has already cleared on this board.',
   'count this tile as complete and roll on.');

update bounty_use set claimed_at = created_at where claimed_at is null;
