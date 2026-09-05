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


def roll_move(from_sequence, board_size, modifier=None):
    """Roll 1d4+1 (or a bounty-modified roll) and clamp to the final tile.

    modifier: None -> single 1d4+1; 'DISADVANTAGE' -> lower of two;
    'ADVANTAGE' -> higher of two; 'DOUBLE_DOWN' -> the two summed (4-10).
    """
    def d():
        return random.randint(1, 4) + 1

    if modifier == 'DISADVANTAGE':
        die = min(d(), d())
    elif modifier == 'ADVANTAGE':
        die = max(d(), d())
    elif modifier == 'DOUBLE_DOWN':
        die = d() + d()
    else:
        die = d()
    return die, min(from_sequence + die, board_size)
