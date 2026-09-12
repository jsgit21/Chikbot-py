"""Pure decision logic for `/candyland roll`.

No Discord, no DB. The cog does the I/O (defer, DB reads, the image gate, the
ceremony) and renders; everything here is a plain function over already-fetched
rows so it can be unit tested without a bot or a database.
"""

import random

# blocking_condition() return values
OUT_OF_SYNC = 'out_of_sync'
FINAL_TILE = 'final_tile'
BOUNTY_PENDING = 'bounty_pending'

# resolve_caller_team() return values
NO_TEAM = 'no_team'
MULTI_TEAM = 'multi_team'


def resolve_caller_team(teams, caller_role_ids):
    """(team_row, None) on a clean match, else (None, NO_TEAM | MULTI_TEAM)."""
    matched = [t for t in teams if t['role_id'] in caller_role_ids]
    if not matched:
        return None, NO_TEAM
    if len(matched) > 1:
        return None, MULTI_TEAM
    return matched[0], None


def blocking_condition(thread_tile_sequence, from_sequence, board_size):
    """A reason the roll cannot proceed, or None if it can."""
    if thread_tile_sequence != from_sequence:
        return OUT_OF_SYNC
    if from_sequence >= board_size:
        return FINAL_TILE
    return None


def _d():
    """One movement die: 1d4 + 1, i.e. 2-5."""
    return random.randint(1, 4) + 1


def roll_move(from_sequence, board_size, modifier=None):
    """Roll 1d4+1 (or a bounty-modified roll) and clamp to the final tile.

    modifier: None -> single 1d4+1; 'DISADVANTAGE' -> lower of two;
    'ADVANTAGE' -> higher of two; 'DOUBLE_DOWN' -> the two summed (4-10).

    The doomsday catch-up is not applied here - see catchup_move, which the cog
    calls with this function's result when a team is eligible.
    """
    if modifier == 'DISADVANTAGE':
        die = min(_d(), _d())
    elif modifier == 'ADVANTAGE':
        die = max(_d(), _d())
    elif modifier == 'DOUBLE_DOWN':
        die = _d() + _d()
    else:
        die = _d()
    return die, min(from_sequence + die, board_size)


# Distance-scaled doomsday catch-up (event-rules decision 37). `gap` is how many
# tiles behind the leader's current tile the team's ordinary roll left it.
# Below CATCHUP_MIN_GAP there is no bonus die. From there the bonus is always
# 1d4, plus a flat modifier that rises by one for every CATCHUP_STEP tiles of
# gap, capped at CATCHUP_MAX_MODIFIER so a genuine blowout still gets help
# without turning back into the teleport decision 37 replaced.
CATCHUP_MIN_GAP = 5
CATCHUP_STEP = 3
CATCHUP_MAX_MODIFIER = 6


def catchup_modifier(gap):
    """The flat modifier on the second-wind 1d4, or None below the threshold."""
    if gap < CATCHUP_MIN_GAP:
        return None
    return min(1 + (gap - CATCHUP_MIN_GAP) // CATCHUP_STEP, CATCHUP_MAX_MODIFIER)


def catchup_move(from_sequence, ordinary_die, leader_tile, board_size):
    """The distance-scaled doomsday catch-up, applied to a team's ordinary roll.

    Call this only when the team is eligible: the reveal has happened, this is
    the team's first roll since it, and the named leader is on a higher tile
    (leader_tile is the leader's current tile).

    gap = leader_tile minus where the ordinary roll landed. Below CATCHUP_MIN_GAP
    there is no catch-up - the ordinary roll stands. From there the team rolls
    one 1d4 plus the scaled modifier (see catchup_modifier) on top of the
    ordinary roll and moves again, clamped to leader_tile - 1: one tile behind
    the leader, never level, never past. The board end also clamps.

    Returns (die, to_sequence, second_wind). second_wind is None when no bonus
    fired, else the modifier that was added (for the announcement). die is the
    ordinary roll unchanged when second_wind is None, else the ordinary roll
    plus the scaled bonus die.
    """
    ordinary_landing = min(from_sequence + ordinary_die, board_size)
    modifier = catchup_modifier(leader_tile - ordinary_landing)
    if modifier is None:
        return ordinary_die, ordinary_landing, None
    die = ordinary_die + random.randint(1, 4) + modifier
    to_sequence = min(from_sequence + die, board_size, leader_tile - 1)
    return die, to_sequence, modifier
