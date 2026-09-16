"""Pure string builders for Candyland's player-facing messages.

No Discord, no DB. Callers pass already-resolved mention strings and already-
fetched values, so this unit-tests without a bot or a database. Mirrors the
shape of candyland_roll.py / candyland_bounty.py.
"""


def header(team_label, subtext):
    """'# Team <label>' + '-# <subtext>'."""
    return f'# Team {team_label}\n-# {subtext}'


def _task_block(label, task_row):
    lines = [f'# __{label}__', f"## {task_row['title']}", f"*{task_row['task']}*"]
    if task_row.get('notes'):
        lines += ['', f"-# *{task_row['notes']}*"]
    return lines


def tile_goals(major, minors):
    """major is a task row: {title, task, notes}. minors is a non-empty list
    of task rows - one for most tiles, two past the doomsday tile. Renders
    the decision-39/42 Major-plus-Minor(s) block Nick specified. A single
    Minor keeps the plain 'Minor Task' label; two or more are numbered."""
    blocks = [_task_block('Major Task', major)]
    label_all = len(minors) > 1
    for i, minor in enumerate(minors, start=1):
        label = f'Minor Task {i}' if label_all else 'Minor Task'
        blocks.append(_task_block(label, minor))

    lines = []
    for i, block in enumerate(blocks):
        if i:
            lines += ['', '']
        lines += block
    return '\n'.join(lines)


def roll_announcement(team_mention, team_label, author_mention, from_sequence,
                      die, dice_art, new_thread_id=None, modifier_name=None,
                      final=False, roll_emoji='🎲', second_wind=None,
                      clamped_at=None, leader_label=None, catchup_declined=False):
    """roll_emoji defaults to the plain dice; callers pass the team's own
    custom emoji when the team has one (team['emoji'])."""
    # second_wind / clamped_at / leader_label are the doomsday "second wind": a
    # distance-scaled bonus die folded into this roll (second_wind is the flat
    # modifier on the 1d4, rendered as 1d4+N), the leader whose lead prompted
    # it, and the tile it stopped on when the bonus would have caught the
    # leader. They compose into the ordinary roll message; a catch-up roll has
    # no announcement of its own.
    #
    # catchup_declined is the team's first roll after the reveal when it was
    # checked for a second wind but the ordinary roll already closed the gap
    # (gap < CATCHUP_MIN_GAP) - no bonus die, but worth telling the team
    # they're close.
    extra_die = second_wind is not None
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
        f'{roll_emoji} {author_mention} has rolled a....{mod_tag}',
        dice_art,
    ]
    if final:
        lines.append('-# 🏁 This is the **final tile**.')
    else:
        if extra_die:
            label = f'1d4+{second_wind}'
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
        elif catchup_declined:
            leader = leader_label or 'the leader'
            lines.append(
                f'-# 🏁 Your team is going just as hard as {leader} - hot on '
                'their tail!'
            )
        if new_thread_id is not None:
            lines.append('')
            lines.append(f"Your team's next tile is ➡️ <#{new_thread_id}>")
    return '\n'.join(lines)


# Custom server emoji; only usable in guilds where it's uploaded.
_VALE_YEP_EMOJI = '<:vale_yep:1532631285497860176>'


def rolling_placeholder(team_mention):
    """Posted immediately on `/candyland roll`, before the tile ceremony runs.
    Edited into the full roll_announcement once the new tile thread exists."""
    return header(team_mention, f'{_VALE_YEP_EMOJI} Moving you to the next tile...')


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


def bounty_roll_announcement(team_mention, author_mention, bounty_name, keep_label,
                             die_a, art_a, die_b, art_b, chosen, reward,
                             new_thread_id=None, final=False, roll_emoji='🎲'):
    """Advantage/Disadvantage bounty-claim announcement: claiming rolls two dice
    immediately and keeps the higher (Advantage) or lower (Disadvantage). Shows
    both dice blocks labelled kept/dropped so the team can see the one that
    didn't count, not just the one that did."""
    lines = [
        header(team_mention, f'{author_mention} completed the **{bounty_name}** bounty!'),
        '',
        f'{roll_emoji} Claiming rolled two dice, keeping the {keep_label}:',
        f'**Roll 1: {die_a}** {"✅ kept" if die_a == chosen else "❌ dropped"}',
        art_a,
        f'**Roll 2: {die_b}** {"✅ kept" if die_b == chosen else "❌ dropped"}',
        art_b,
        '',
        f'### {reward}',
    ]
    if final:
        lines.append('-# 🏁 This is the **final tile**.')
    elif new_thread_id is not None:
        lines.append('')
        lines.append(f"Your team's next tile is ➡️ <#{new_thread_id}>")
    return '\n'.join(lines)


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
