import datetime

from ..shared import tz


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
    if comp_type == 'botw':
        return f'{gained:,} KC'
    return f'{gained:,} XP'


def build_results_post(botw_winner, sotw_winner):
    """Return the text of the competition results announcement.

    botw_winner / sotw_winner: dicts from winners.resolve_winner(), or None.
    Linked winners are @mentioned; unlinked winners are shown as plain @rsn.
    """
    lines = ['**Competition Results**', '']

    if botw_winner:
        mention = _mention(botw_winner)
        label = _gained_label('botw', botw_winner.get('gained'))
        lines.append(f'**BOTW** — {mention} with **{label}** (`{botw_winner["rsn"]}`)')
    else:
        lines.append('**BOTW** — no winner data available')

    if sotw_winner:
        mention = _mention(sotw_winner)
        label = _gained_label('sotw', sotw_winner.get('gained'))
        lines.append(f'**SOTW** — {mention} with **{label}** (`{sotw_winner["rsn"]}`)')
    else:
        lines.append('**SOTW** — no winner data available')

    lines += [
        '',
        "Congrats to both winners! Each winner picks the next cycle's opposite event target.",
    ]

    return '\n'.join(lines)


def _to_et(dt_utc):
    return dt_utc.replace(tzinfo=datetime.timezone.utc).astimezone(tz.ET)


def _format_dt(dt_et):
    # Portable equivalent of strftime('%-m/%-d %-I:%M %p') — Windows lacks '-'.
    hour12 = dt_et.hour % 12 or 12
    return f'{dt_et.strftime("%a")} {dt_et.month}/{dt_et.day} {hour12}:{dt_et.minute:02d} {dt_et.strftime("%p")}'


def build_kickoff_post(starts_at, ends_at, botw, sotw):
    """Return the text of the next cycle's kickoff announcement.

    starts_at / ends_at: naive UTC datetimes for the new cycle window.
    botw / sotw: dicts with 'title' (the WOM competition title), 'metric_display',
    and 'picker_text' (the picker's @mention or plain alias/name).
    """
    start_et = _to_et(starts_at)
    end_et = _to_et(ends_at)

    lines = [
        'GM everyone! :sunny:',
        '',
        'The next BOTW/SOTW rotation is scheduled:',
        '',
        f'**BOTW** — {botw["title"]} (picked by {botw["picker_text"]})',
        f'**SOTW** — {sotw["title"]} (picked by {sotw["picker_text"]})',
        '',
        f'Runs **{_format_dt(start_et)}** → **{_format_dt(end_et)} ET**',
        '',
        "-# It's all for fun, good luck and have fun training/bossing!",
    ]

    return '\n'.join(lines)
