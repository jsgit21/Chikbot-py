import asyncio

from . import db as comp_db, types, wom_api


async def get_competitions_by_type(cycle_id):
    """Fetch every competition row for cycle_id, resolve each row's live WOM
    detail, and group by inferred CompetitionType.key.

    Returns (by_type, fetch_errors):
      by_type: {type_key: [(row, detail), ...]} for rows whose detail fetch
      succeeded and whose title matched a known type.
      fetch_errors: [(row, exception), ...] for rows whose WOM fetch raised.
      Excluded from by_type. Callers that want to abort loudly on a fetch
      failure (matching ApproveKickoffButton's existing behavior) should
      check this list themselves; callers that want to silently skip
      (matching create_otw's and _resolve_nominator's existing behavior)
      can ignore it.
    """
    comps = await asyncio.to_thread(comp_db.get_competitions_for_cycle, cycle_id)
    by_type = {}
    fetch_errors = []
    for row in comps:
        try:
            detail = await asyncio.to_thread(wom_api.get_competition, row['competition_id'])
        except Exception as exc:
            fetch_errors.append((row, exc))
            continue
        comp_type = types.infer_type_from_title(detail.get('title', ''))
        if comp_type:
            by_type.setdefault(comp_type.key, []).append((row, detail))
    return by_type, fetch_errors
