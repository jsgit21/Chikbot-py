-- Adds the CHARGE bounty's task/reward text for both boards, and corrects the
-- Advantage/Disadvantage reward text now that claiming them rolls immediately
-- instead of deferring to the team's next /candyland roll.
--
-- Run against BOTH schemas, e.g.:
--   mysql candyland      < 2026-09-16_charge_bounty_and_reward_wording.sql
--   mysql candyland_test < 2026-09-16_charge_bounty_and_reward_wording.sql
--
-- No preconditions.

insert into bounty (board_number, bounty_key, task, reward) values
  (1, 'CHARGE',
   'your team must have 6 individual players complete The Fremennik Way combat achievement.',
   'move forward 4 tiles - no roll required.'),
  (2, 'CHARGE',
   'your team must complete a deathless 300+ Tombs of Amascut with 8 people.',
   'move forward 4 tiles - no roll required.');

update bounty
   set reward = 'roll twice immediately and take the lower result.'
 where bounty_key = 'DISADVANTAGE';

update bounty
   set reward = 'roll twice immediately and take the higher result.'
 where bounty_key = 'ADVANTAGE';
