-- Replace the doomsday teleport with a clamped extra-die catch-up roll.
--
-- Adds the 'catchup_roll' value to movement.kind. The post-reveal catch-up (one
-- extra 1d4+1 on a trailing team's next roll, clamped to the team ahead) writes
-- a real dice movement row, so it needs its own kind distinct from 'roll'.
--
-- Run against BOTH schemas, e.g.:
--   mysql candyland      < 2026-09-08_catchup_roll.sql
--   mysql candyland_test < 2026-09-08_catchup_roll.sql
--
-- No preconditions and no data touch: 'catchup_roll' is a new value and nothing
-- is written with it until the code shipped alongside this migration runs. Any
-- pre-existing 'board_transition' teleport rows stay as they are and still fold.

alter table movement
  modify kind enum('roll','adjustment','board_transition','catchup_roll') not null;
