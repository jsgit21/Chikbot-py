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
                      final=False, extra_die=False, clamped_at=None,
                      blocked_by=None):
    # extra_die, clamped_at and blocked_by are the doomsday catch-up's display
    # notes: an extra 1d4+1 folded into this roll, and (when the roll clamped
    # against the team ahead) the tile it stopped on plus that team's label.
    # They compose into the ordinary roll message; a catch-up roll has no
    # announcement of its own.
    if modifier_name and extra_die:
        mod_tag = f' _(with {modifier_name} and a bonus die)_'
    elif extra_die:
        mod_tag = ' _(with a bonus die)_'
    elif modifier_name:
        mod_tag = f' _(with {modifier_name})_'
    else:
        mod_tag = ''
    lines = [
        header(team_mention, f'{team_label} has completed Tile {from_sequence}'),
        '',
        f'🎲 {author_mention} has rolled a....{mod_tag}',
        dice_art,
    ]
    if final:
        lines.append('-# 🏁 This is the **final tile**.')
    else:
        if clamped_at is not None:
            if blocked_by:
                lines.append(
                    f'-# 🏁 The road ahead is blocked, it looks like team '
                    f'{blocked_by} is standing in your way at tile {clamped_at}!'
                )
            else:
                lines.append(
                    f'-# 🏁 Pulled level with the team ahead at tile {clamped_at}.'
                )
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
