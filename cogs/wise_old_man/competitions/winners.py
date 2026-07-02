from ..identity import db as identity_db
from . import db as comp_db


def _winner_from_participations(participations):
    """Return the participation dict with the highest progress.gained, or None."""
    active = [p for p in participations if p.get('progress', {}).get('gained') is not None]
    if not active:
        return None
    return max(active, key=lambda p: p['progress']['gained'])


def resolve_winner(competition_detail, testdb=None):
    """Resolve the winner from a GET /competitions/{id} response.

    Returns:
        {
            'competition_id': int,
            'wom_user_id':    int,
            'rsn':            str,
            'gained':         int,
            'discord_user_id': int or None,
            'alias':           str or None,
        }
    or None if there are no participations with recorded progress.
    """
    comp_id = competition_detail['id']
    participations = competition_detail.get('participations', [])
    top = _winner_from_participations(participations)
    if top is None:
        return None

    player = top['player']
    wom_user_id = player['id']
    rsn = player['displayName']
    gained = top['progress']['gained']

    identity = identity_db.discord_user_for_wom_id(wom_user_id, testdb=testdb)

    return {
        'competition_id': comp_id,
        'wom_user_id': wom_user_id,
        'rsn': rsn,
        'gained': gained,
        'discord_user_id': identity['user_id'] if identity else None,
        'alias': identity['preferred_alias'] if identity else None,
    }


def resolve_winners(botw_detail, sotw_detail, testdb=None):
    """Resolve both winners. Returns (botw_winner, sotw_winner, conflicts).

    Each winner is the dict from resolve_winner(), or None.
    conflicts is a list of human-readable warning strings for the mod.
    """
    conflicts = []

    botw_winner = resolve_winner(botw_detail, testdb=testdb)
    sotw_winner = resolve_winner(sotw_detail, testdb=testdb)

    if botw_winner is None:
        conflicts.append('No BOTW participants with recorded progress.')
    elif botw_winner['discord_user_id'] is None:
        conflicts.append(
            f'BOTW winner `{botw_winner["rsn"]}` has no Discord link — link via `/wom link` before approving.'
        )

    if sotw_winner is None:
        conflicts.append('No SOTW participants with recorded progress.')
    elif sotw_winner['discord_user_id'] is None:
        conflicts.append(
            f'SOTW winner `{sotw_winner["rsn"]}` has no Discord link — link via `/wom link` before approving.'
        )

    return botw_winner, sotw_winner, conflicts


def resolve_winner_from_fallback(parsed, comp_id, testdb=None):
    """Build a winner dict from an event_calendar parsed result.

    Used when the WOM API is unavailable. RSN is resolved to wom_user_id via
    wom_group; identity resolved via wom_link.

    Returns the same shape as resolve_winner(), or None if the parsed result
    has no winner RSN.
    """
    if not parsed or not parsed.get('winner_rsn'):
        return None

    rsn = parsed['winner_rsn']
    wom_user_id = comp_db.get_wom_id_for_rsn(rsn, testdb=testdb)
    identity = (
        identity_db.discord_user_for_wom_id(wom_user_id, testdb=testdb)
        if wom_user_id else None
    )

    return {
        'competition_id': comp_id,
        'wom_user_id': wom_user_id,
        'rsn': rsn,
        'gained': parsed.get('winner_gained'),
        'discord_user_id': identity['user_id'] if identity else None,
        'alias': identity['preferred_alias'] if identity else None,
    }


def resolve_winners_from_fallback(botw_parsed, sotw_parsed, botw_comp_id, sotw_comp_id, testdb=None):
    """Fallback version of resolve_winners using event_calendar results."""
    conflicts = []

    botw_winner = resolve_winner_from_fallback(botw_parsed, botw_comp_id, testdb=testdb)
    sotw_winner = resolve_winner_from_fallback(sotw_parsed, sotw_comp_id, testdb=testdb)

    if botw_winner is None:
        conflicts.append('BOTW winner could not be parsed from event-calendar fallback.')
    elif botw_winner['discord_user_id'] is None:
        conflicts.append(
            f'BOTW winner `{botw_winner["rsn"]}` has no Discord link — link via `/wom link` before approving.'
        )

    if sotw_winner is None:
        conflicts.append('SOTW winner could not be parsed from event-calendar fallback.')
    elif sotw_winner['discord_user_id'] is None:
        conflicts.append(
            f'SOTW winner `{sotw_winner["rsn"]}` has no Discord link — link via `/wom link` before approving.'
        )

    conflicts.append('Winners sourced from event-calendar fallback (WOM API was unavailable) — verify before approving.')

    return botw_winner, sotw_winner, conflicts
