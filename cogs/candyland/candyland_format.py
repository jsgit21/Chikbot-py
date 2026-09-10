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
                      catchup_band=None, leader_label=None):
    # extra_die / catchup_band / clamped_at / leader_label are the doomsday
    # "second wind": a distance-scaled bonus die folded into this roll
    # (catchup_band is (threshold, die_label), only the label is shown), the
    # leader whose lead prompted it, and the tile it stopped on when the bonus
    # would have caught the leader. They compose into the ordinary roll message;
    # a catch-up roll has no announcement of its own.
    if modifier_name and extra_die:
        mod_tag = f' _(with {modifier_name} and a second wind)_'
    elif extra_die:
        mod_tag = ' _(with a second wind)_'
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
        if extra_die and catchup_band is not None:
            label = catchup_band[1]
            leader = leader_label or 'the leader'
            line = (
                f'-# 🏁 Seeing how much progress {leader} is making has given '
                f'your team a **{label}** second wind!'
            )
            if clamped_at is not None:
                line += (
                    f" Your team pulls right up on the leader's tail at tile "
                    f'{clamped_at}, but they blocked the way ahead!'
                )
            lines.append(line)
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
