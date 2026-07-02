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
