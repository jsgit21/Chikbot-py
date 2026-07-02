import os

from ..shared import wom_http


def list_group_competitions():
    group_id = os.getenv('WOM_GROUPID')
    return wom_http.get(f'/groups/{group_id}/competitions')


def get_competition(competition_id):
    return wom_http.get(f'/competitions/{competition_id}')


def find_ended_competition_pair(competitions):
    """Return (botw_summary, sotw_summary) from a list of group competition summaries.

    Searches the most recently ended competitions matching our title patterns.
    Returns (None, None) if the pair cannot be found.
    """
    ended = [c for c in competitions if c.get('status') == 'finished']
    ended.sort(key=lambda c: c['endsAt'], reverse=True)

    botw = next(
        (c for c in ended if 'boss of the week' in c['title'].lower()), None
    )
    sotw = next(
        (c for c in ended if 'skill of the week' in c['title'].lower()), None
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
