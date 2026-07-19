from textwrap import dedent

from shared.emojis import GM_EMOJI

from . import types


def _mention(winner):
    """@mention if linked; plain @rsn if not."""
    if winner and winner.get('discord_user_id'):
        return f'<@{winner["discord_user_id"]}>'
    if winner and winner.get('rsn'):
        return f'@{winner["rsn"]}'
    return '@unknown'


def _gained_label(comp_type, gained):
    if gained is None:
        return 'unknown'
    return f'{gained:,} {comp_type.gained_unit}'


def build_result_post(comp_type, winner):
    """Return the text of a standalone competition results announcement.

    winner: dict from winners.resolve_winner(), or None.
    A linked winner is @mentioned; an unlinked one is shown as plain @rsn.
    """
    lines = [f'**{comp_type.display_name} Results**', '']

    if winner:
        mention = _mention(winner)
        label = _gained_label(comp_type, winner.get('gained'))
        lines.append(f'{mention} with **{label}** (`{winner["rsn"]}`)')
        lines += [
            '',
            f"Congrats! Your pick decides next cycle's "
            f'{types.TYPES[comp_type.feeds_picker_for].display_name} target.',
        ]
    else:
        lines.append('No winner data available.')

    return '\n'.join(lines)


def _format_dt(dt_et):
    # Portable equivalent of strftime('%-m/%-d %-I:%M %p') — Windows lacks '-'.
    hour12 = dt_et.hour % 12 or 12
    return f'{dt_et.strftime("%a")} {dt_et.month}/{dt_et.day} {hour12}:{dt_et.minute:02d} {dt_et.strftime("%p")}'


def build_kickoff_post(starts_at, ends_at, botw, sotw):
    """Return the text of the next cycle's kickoff announcement.

    starts_at / ends_at: naive ET (server-local) datetimes for the new cycle window.
    botw / sotw: dicts with 'title' (the WOM competition title), 'metric_display',
    and 'picker_text' (the picker's @mention or plain alias/name).
    """
    return dedent(f"""\
        {GM_EMOJI} everyone!

        The next BOTW/SOTW rotation is scheduled:

        **BOTW** — {botw["title"]} (picked by {botw["picker_text"]})
        **SOTW** — {sotw["title"]} (picked by {sotw["picker_text"]})

        Runs **{_format_dt(starts_at)}** → **{_format_dt(ends_at)} ET**

        -# It's all for fun, good luck and have fun training/bossing!""")
