import re

# Matches competition URLs in message text or embed fields.
_COMP_URL_RE = re.compile(r'wiseoldman\.net/competitions/(\d+)')

# Matches a participant line like "1. PlayerName — 1,234" or "🥇 PlayerName - 1234 KC".
# Captures the player name and the numeric score.
_PARTICIPANT_RE = re.compile(
    r'^\s*(?:\d+[.)]\s+|[🥇🥈🥉]\s+)?(.+?)\s*[-—–]\s*([\d,]+)',
    re.MULTILINE,
)


def _extract_competition_id(text):
    m = _COMP_URL_RE.search(text)
    return int(m.group(1)) if m else None


def _extract_top_participant(text):
    """Return (rsn, gained_int) for the first listed participant, or None."""
    for m in _PARTICIPANT_RE.finditer(text):
        rsn = m.group(1).strip()
        try:
            gained = int(m.group(2).replace(',', ''))
        except ValueError:
            continue
        return rsn, gained
    return None


def parse_result_message(message):
    """Parse a WOM bot competition result Discord message.

    Searches the message content and all embed fields for a competition URL
    and a ranked participant list. Trusts only messages already filtered to
    WOM_DISCORD_BOT_ID by the caller.

    Returns a dict:
        {
            'competition_id': int or None,
            'winner_rsn':     str or None,
            'winner_gained':  int or None,
        }
    """
    texts = [message.content or '']
    for embed in message.embeds:
        for field_text in (embed.title, embed.url, embed.description):
            if field_text:
                texts.append(field_text)
        for field in embed.fields:
            if field.value:
                texts.append(field.value)

    combined = '\n'.join(texts)
    competition_id = _extract_competition_id(combined)

    participant = _extract_top_participant(combined)
    winner_rsn, winner_gained = participant if participant else (None, None)

    return {
        'competition_id': competition_id,
        'winner_rsn': winner_rsn,
        'winner_gained': winner_gained,
    }
