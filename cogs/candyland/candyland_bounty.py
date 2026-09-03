"""Pure decision logic for `/candyland bounty`.

No Discord, no DB. The cog does the I/O and the DB layer does the write; this is
plain functions and tables so it unit-tests without a bot or a database.

Effect *text* (tasks, rewards) is authored in casual-gmers content, not here.
What lives here is the mechanical shape chikbot must apply.
"""

BOUNTY_KEYS = [
    'RETREAT', 'ADVANCE', 'DISADVANTAGE', 'ADVANTAGE', 'DOUBLE_DOWN', 'SWAP',
]

BOUNTY_NAMES = {
    'RETREAT': 'Retreat',
    'ADVANCE': 'Advance',
    'DISADVANTAGE': 'Disadvantage',
    'ADVANTAGE': 'Advantage',
    'DOUBLE_DOWN': 'Double Down',
    'SWAP': 'Swap',
}

# One-line mechanical summary for the tile-thread confirmation. Not the
# authoritative reward text - that is in casual-gmers content.
BOUNTY_MECHANIC = {
    'RETREAT': 'Team moves back 1 tile now.',
    'ADVANCE': 'Team moves forward 1 tile now.',
    'DISADVANTAGE': 'Next roll is the lower of two 1d4+1.',
    'ADVANTAGE': 'Next roll is the higher of two 1d4+1.',
    'DOUBLE_DOWN': ('Next roll is two 1d4+1 summed (4-10). '
                    'First complete this tile a second time - '
                    'full Major and Minor, fresh proof.'),
    'SWAP': 'This tile is cleared. The team rolls normally next.',
}

# All six bounties open a fresh, labelled thread on the destination tile and
# archive the one the team was on, so the alternative task's proof always
# starts from an empty thread.
#
# Disadvantage and Advantage are still special on one axis: sequencing. A team
# may not chain bounties across one tile, but a +/-1 move (Retreat/Advance) may
# still follow one of these two. Every other bounty is a hard stop until the
# team completes the tile and rolls. Enforced in the cog off
# get_last_bounty_since_roll.
SOFT_LOCK_KEYS = {'DISADVANTAGE', 'ADVANTAGE'}
MOVE_KEYS = {'RETREAT', 'ADVANCE'}


def destination(bounty_key, from_sequence, board_final):
    """The tile the team ends on after claiming. Equals from_sequence for the
    four non-moving bounties."""
    if bounty_key == 'RETREAT':
        return max(1, from_sequence - 1)
    if bounty_key == 'ADVANCE':
        return min(from_sequence + 1, board_final)
    return from_sequence
