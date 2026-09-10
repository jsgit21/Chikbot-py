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


def catchup_move(from_sequence, ordinary_die, blocker_tile, board_size):
    """The doomsday catch-up, applied to a team's ordinary roll.

    Call this only when the team is eligible: the reveal has happened, this is
    the team's first roll since it, and at least one other team is on a higher
    tile (blocker_tile is the lowest such tile).

    If the ordinary roll already lands the team within 2 tiles of blocker_tile,
    level with it, or past it, there is no catch-up: the ordinary roll stands.
    Otherwise one more 1d4+1 is added and the destination is clamped to
    blocker_tile - 1 - one tile behind the team ahead, never level, never past.

    Returns (die, to_sequence), same shape as roll_move. die is the ordinary
    roll unchanged when no catch-up applied, or the ordinary roll plus the
    extra 1d4+1 when it did.
    """
    ordinary_landing = min(from_sequence + ordinary_die, board_size)
    if blocker_tile - ordinary_landing <= 2:
        return ordinary_die, ordinary_landing
    die = ordinary_die + _d()
    return die, min(from_sequence + die, board_size, blocker_tile - 1)
