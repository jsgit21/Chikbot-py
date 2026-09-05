"""Pure string builders for Candyland's player-facing messages.

No Discord, no DB. Callers pass already-resolved mention strings and already-
fetched values, so this unit-tests without a bot or a database. Mirrors the
shape of candyland_roll.py / candyland_bounty.py.
"""


def header(team_label, subtext):
    """'# Team <label>' + '-# <subtext>'."""
    return f'# Team {team_label}\n-# {subtext}'


def roll_announcement(team_mention, team_label, author_mention, from_sequence,
                      die, dice_art, new_thread_id=None, modifier_name=None,
                      final=False):
    mod_tag = f' _(with {modifier_name})_' if modifier_name else ''
    lines = [
        header(team_mention, f'{team_label} has completed Tile {from_sequence}'),
        '',
        f'🎲 {author_mention} has rolled a....{mod_tag}',
        dice_art,
    ]
    if final:
        lines.append('-# 🏁 This is the **final tile**.')
    elif new_thread_id is not None:
        lines.append('')
        lines.append(f"Your team's next tile is ➡️ <#{new_thread_id}>")
    return '\n'.join(lines)


def teleport_announcement(team_mention, team_label, author_mention, past_tile,
                          to_sequence, new_thread_id=None):
    lines = [
        header(team_mention, f'{team_label} was pulled onto the road past tile {past_tile}'),
        '',
        f'{author_mention} pulled **{team_label}** forward to tile {to_sequence}.',
    ]
    if new_thread_id is not None:
        lines.append('')
        lines.append(f"Your team's next tile is ➡️ <#{new_thread_id}>")
    return '\n'.join(lines)


def bounty_taken(team_mention, author_mention, bounty_name, task, reward):
    return '\n'.join([
        header(team_mention, f'{author_mention} has chosen to take a bounty!'),
        '',
        f'### The **{bounty_name}** bounty has been redeemed.',
        f'-# This means that {task}',
        '',
        '### If you complete this challenge your team will:',
        f'-# {reward}',
    ])


def bounty_claimed(team_mention, author_mention, bounty_name, reward, new_thread_id):
    return '\n'.join([
        header(team_mention, f'{author_mention} completed the **{bounty_name}** bounty!'),
        '',
        f'### {reward}',
        '',
        f"Your team's next tile is ➡️ <#{new_thread_id}>",
    ])


def bounties_list(team_mention, bounty_rows):
    """bounty_rows: iterable of (key, name, used) in display order."""
    lines = [header(team_mention, 'The bounties your team has available are:'), '']
    for _key, name, used in bounty_rows:
        lines.append(f'~~{name}~~' if used else f'**{name}**')
    lines.append('')
    lines.append('-# You can use `/candyland bounty-info [bounty name]` for details.')
    return '\n'.join(lines)


def final_tile(team_mention, team_label, planner_role_mention, moderator_role_mention,
              claim):
    """claim=False is the tile-42 doomsday cue; claim=True is the tile-65 win claim."""
    if claim:
        subtext = f'{team_label} has claimed the final tile.'
        cue = f'{planner_role_mention} {moderator_role_mention} — verify this claim.'
        detail_lines = [
            f'-# **{team_label}** says they finished the last tile. Check their submissions',
            '-# and confirm.',
        ]
    else:
        subtext = f'{team_label} has completed the final tile.'
        cue = f'{planner_role_mention} {moderator_role_mention} — the road ends here.'
        detail_lines = [
            f'-# **{team_label}** has reached the end of what they know. Something is',
            '-# waiting for whoever goes first.',
        ]
    return '\n'.join([
        header(team_mention, subtext),
        '',
        f'### {cue}',
        *detail_lines,
    ])


def manual_move(team_mention, from_sequence, to_sequence, bounty_cleared):
    lines = [header(team_mention, f'moved from tile {from_sequence} to {to_sequence} by a moderator.')]
    if bounty_cleared:
        lines.append("-# The team's outstanding bounty was cleared so it can roll again.")
    return '\n'.join(lines)
