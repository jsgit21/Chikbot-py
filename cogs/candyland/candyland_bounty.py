"""Pure decision logic for `/candyland bounty`.

No Discord, no DB. The cog does the I/O and the DB layer does the write; this is
plain functions and tables so it unit-tests without a bot or a database.

Effect *text* (tasks, rewards) is authored in casual-gmers content, not here.
What lives here is the mechanical shape chikbot must apply.
"""

BOUNTY_KEYS = [
    'RETREAT', 'ADVANCE', 'CHARGE', 'DISADVANTAGE', 'ADVANTAGE', 'DOUBLE_DOWN', 'SWAP',
]

BOUNTY_NAMES = {
    'RETREAT': 'Retreat',
    'ADVANCE': 'Advance',
    'CHARGE': 'Charge',
    'DISADVANTAGE': 'Disadvantage',
    'ADVANTAGE': 'Advantage',
    'DOUBLE_DOWN': 'Double Down',
    'SWAP': 'Swap',
}

# Advantage/Disadvantage no longer defer to the next /candyland roll - claiming
# them rolls (two dice, keep higher/lower) and moves the team right away, so
# the claim itself is the roll. complete_bounty special-cases these two keys
# instead of going through destination().
ROLL_ON_CLAIM_KEYS = {'ADVANTAGE', 'DISADVANTAGE'}
KEEP_LABEL = {'ADVANTAGE': 'higher', 'DISADVANTAGE': 'lower'}


def destination(bounty_key, from_sequence, board_final):
    """The tile the team ends on after claiming. Equals from_sequence for the
    three non-moving bounties (Advantage/Disadvantage now resolve in
    complete_bounty instead of here - see ROLL_ON_CLAIM_KEYS)."""
    if bounty_key == 'RETREAT':
        return max(1, from_sequence - 1)
    if bounty_key == 'ADVANCE':
        return min(from_sequence + 1, board_final)
    if bounty_key == 'CHARGE':
        return min(from_sequence + 4, board_final)
    return from_sequence
