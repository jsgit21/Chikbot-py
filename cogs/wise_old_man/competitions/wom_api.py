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


def find_ended_competitions(competitions, now=None, lookback_days=14):
    """Return group competition summaries that ended within the last lookback_days.

    The WOM group-competitions list has no 'status' field, so "ended" is
    derived from endsAt vs now rather than filtered from the API response.
    No title matching or window correlation — this is only the fallback for
    competitions created directly on WOM's site rather than through
    /competition create, which have no DB row to check against otherwise.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=lookback_days)
    return [
        c for c in competitions
        if (ea := _parse_ends_at(c)) and cutoff < ea <= now
    ]


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
