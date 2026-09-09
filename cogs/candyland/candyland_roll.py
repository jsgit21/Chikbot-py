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


def roll_move(from_sequence, board_size, modifier=None, ceiling=None,
              extra_die=False):
    """Roll 1d4+1 (or a bounty-modified roll) and clamp to the final tile.

    modifier: None -> single 1d4+1; 'DISADVANTAGE' -> lower of two;
    'ADVANTAGE' -> higher of two; 'DOUBLE_DOWN' -> the two summed (4-10).

    extra_die: the doomsday catch-up. When true one more 1d4+1 is added on top of
    whatever the modifier produced. It stacks with any modifier rather than
    replacing it, so an Advantage catch-up is max(d(), d()) + d().

    ceiling: an optional upper tile the destination cannot pass, clamped together
    with the board end. The catch-up roll passes the lowest tile occupied by a
    team ahead so a caught-up team lands level with it, never past it. None means
    only the board end clamps.
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
    if extra_die:
        die += d()
    limit = board_size if ceiling is None else min(board_size, ceiling)
    return die, min(from_sequence + die, limit)
