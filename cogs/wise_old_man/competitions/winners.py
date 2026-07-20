from ..identity import db as identity_db


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


def _merge_participations(participations_a, participations_b):
    """Merge two competitions' participations by stable WOM player id, summing
    progress.gained. A player needs recorded progress in at least one half to
    appear at all -- mirrors _winner_from_participations' "no progress = not a
    participant" rule, applied per-half instead of per-competition.
    """
    totals = {}
    for participations in (participations_a, participations_b):
        for p in participations:
            gained = p.get('progress', {}).get('gained')
            if gained is None:
                continue
            entry = totals.setdefault(p['player']['id'], {'player': p['player'], 'gained': 0})
            entry['gained'] += gained
    return totals


def resolve_combined_winner(detail_a, detail_b, testdb=None):
    """Resolve a 'sum' raid pair's winner (CoX, ToB): highest combined
    completions across both halves. 'competition_id' in the return is
    detail_a's id, by caller convention (resolve_paired_winner always passes
    the base-mode half as detail_a) -- kept for return-shape parity with
    resolve_winner(), no caller reads it for a paired result today.
    """
    totals = _merge_participations(
        detail_a.get('participations', []), detail_b.get('participations', [])
    )
    if not totals:
        return None

    winner_id, entry = max(totals.items(), key=lambda kv: kv[1]['gained'])
    identity = identity_db.discord_user_for_wom_id(winner_id, testdb=testdb)
    return {
        'competition_id': detail_a['id'],
        'wom_user_id': winner_id,
        'rsn': entry['player']['displayName'],
        'gained': entry['gained'],
        'discord_user_id': identity['user_id'] if identity else None,
        'alias': identity['preferred_alias'] if identity else None,
    }


def resolve_max_of_winner(detail_a, detail_b, testdb=None):
    """Resolve a 'max' raid pair's winner (ToA): the higher of each half's
    independently-resolved top scorer -- no summing. Ties favor detail_a (by
    convention, the base/Normal-mode half); arbitrary but explicit, consistent
    with _winner_from_participations' own no-tiebreak max() elsewhere here.
    """
    winner_a = resolve_winner(detail_a, testdb=testdb)
    winner_b = resolve_winner(detail_b, testdb=testdb)
    if winner_a is None:
        return winner_b
    if winner_b is None:
        return winner_a
    return winner_a if winner_a['gained'] >= winner_b['gained'] else winner_b


def resolve_paired_winner(pair, detail_a, detail_b, testdb=None):
    """Resolve a raid pair's winner per pair.rule. Pass the base-mode half as
    detail_a (order doesn't matter for 'max', matters for 'sum''s competition_id).
    """
    if pair.rule == 'sum':
        return resolve_combined_winner(detail_a, detail_b, testdb=testdb)
    if pair.rule == 'max':
        return resolve_max_of_winner(detail_a, detail_b, testdb=testdb)
    raise ValueError(f'Unknown raid pair rule: {pair.rule!r}')
