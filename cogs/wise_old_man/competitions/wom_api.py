import datetime
import os
from urllib.parse import quote

from ..shared import wom_http


def list_group_competitions():
    group_id = os.getenv('WOM_GROUPID')
    return wom_http.get(f'/groups/{group_id}/competitions')


def get_player(rsn):
    """Fetch a player's full details, including latestSnapshot.data (skills/bosses/activities)."""
    return wom_http.get(f'/players/{quote(rsn)}')


def get_competition(competition_id):
    return wom_http.get(f'/competitions/{competition_id}')


def _parse_ends_at(competition):
    raw = competition.get('endsAt')
    if not raw:
        return None
    try:
        return datetime.datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None


def find_ended_competition_pair(competitions, now=None):
    """Return (botw_summary, sotw_summary) from a list of group competition summaries.

    The WOM group-competitions list has no 'status' field, so "ended" is
    derived from endsAt vs now rather than filtered from the API response.
    Searches the most recently ended BOTW, then the SOTW sharing its exact
    start/end window (both events in a cycle are created with identical
    startsAt/endsAt), so a stray old finished competition can't get paired with
    a current one. Returns (None, None) or (botw, None) if no matching pair
    is found.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    ended = [c for c in competitions if (ea := _parse_ends_at(c)) and ea < now]
    ended.sort(key=lambda c: c.get('endsAt', ''), reverse=True)

    botw = next(
        (c for c in ended if 'boss of the week' in c.get('title', '').lower()), None
    )
    if botw is None:
        return None, None

    sotw = next(
        (c for c in ended
         if 'skill of the week' in c.get('title', '').lower()
         and c.get('startsAt') == botw.get('startsAt')
         and c.get('endsAt') == botw.get('endsAt')),
        None,
    )
    return botw, sotw


def create_competition(title, metric, starts_at, ends_at):
    """POST a new competition to WOM.

    starts_at and ends_at must be ISO-8601 UTC strings (e.g. '2026-07-04T14:00:00.000Z').
    Returns the full response body: { competition: {...}, verificationCode: '...' }.
    """
    group_id = os.getenv('WOM_GROUPID')
    verification_code = os.getenv('WOM_GROUP_VERIFICATION_CODE')
    payload = {
        'title': title,
        'metric': metric,
        'startsAt': starts_at,
        'endsAt': ends_at,
        'groupId': int(group_id),
        'groupVerificationCode': verification_code,
    }
    return wom_http.post('/competitions', json=payload)
