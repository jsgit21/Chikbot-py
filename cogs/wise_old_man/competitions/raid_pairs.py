"""Registry of OSRS raids with a "split" WOM metric (base mode + hard mode as
separate metric slugs) and the rule used to resolve one BOTW winner across
both underlying WOM competitions. WOM tracks one metric per competition, so
a BOTW pick of one of these six slugs needs two linked competitions (see
competitions_cog.py's _build_side) and, at winner-detection time, needs its
sibling half found and combined into one draft (see competitions_cog.py's
_handle_raid_pair_candidate) instead of being processed alone.
"""

import asyncio
import dataclasses
import datetime

from . import wom_api

# Small buffer for pairs created manually on WOM's site, where a mod might type
# the same endsAt into two separate competition forms a few minutes apart.
# Bot-created pairs always match exactly (both created in one command, same
# starts_at/ends_at), so this only matters for the manual case.
SIBLING_TOLERANCE = datetime.timedelta(minutes=5)

# If a pass-1 (DB-tracked) raid-pair half has been ended with no sibling found
# for this long, treat it as orphaned and fail loud instead of retrying forever.
# Matches wom_api.find_ended_competitions' own lookback_days default.
ORPHAN_ESCALATION_DAYS = 14


@dataclasses.dataclass(frozen=True)
class RaidPair:
    base_metric: str
    hard_metric: str
    base_label: str    # short, WOM-title-safe label for the base-mode half, e.g. 'CoX'
    hard_label: str    # short, WOM-title-safe label for the hard-mode half, e.g. 'CoX (CM)'
    rule: str            # 'sum' (CoX/ToB) or 'max' (ToA)
    display_name: str    # short name for chat/log/draft messages, e.g. 'CoX'


_PAIRS = [
    RaidPair('chambers_of_xeric', 'chambers_of_xeric_challenge_mode',
             'CoX', 'CoX (CM)', 'sum', 'CoX'),
    RaidPair('theatre_of_blood', 'theatre_of_blood_hard_mode',
             'ToB', 'ToB (HM)', 'sum', 'ToB'),
    RaidPair('tombs_of_amascut', 'tombs_of_amascut_expert',
             'ToA', 'ToA (Expert)', 'max', 'ToA'),
]

RAID_PAIRS = {}
for _p in _PAIRS:
    RAID_PAIRS[_p.base_metric] = _p
    RAID_PAIRS[_p.hard_metric] = _p
del _p


def pair_for_metric(metric_slug):
    """Return the RaidPair this metric belongs to, or None."""
    return RAID_PAIRS.get(metric_slug)


def partner_metric(metric_slug):
    """Return the sibling metric slug for a split-raid metric, or None."""
    pair = pair_for_metric(metric_slug)
    if pair is None:
        return None
    return pair.hard_metric if metric_slug == pair.base_metric else pair.base_metric


def label_for_metric(metric_slug):
    """Return the short title-safe label for one half of a raid pair, or None."""
    pair = pair_for_metric(metric_slug)
    if pair is None:
        return None
    return pair.base_label if metric_slug == pair.base_metric else pair.hard_label


def _parse_iso(iso_str):
    """Parse an ISO-8601 UTC string from the WOM API into a naive UTC datetime."""
    return datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00')).replace(tzinfo=None)


async def find_sibling(this_detail, competitions):
    """Search `competitions` (a wom_api.list_group_competitions() result) for
    this_detail's raid-pair sibling: same partner metric, endsAt within
    SIBLING_TOLERANCE. Returns None if this_detail's metric isn't a split-raid
    slug, or no matching sibling is currently on WOM. Fetches full detail (one
    wom_api.get_competition call per endsAt-matching candidate, typically 0 or
    1) to confirm metric, since list summaries aren't relied on for metric
    anywhere else in this codebase today.
    """
    pair = pair_for_metric(this_detail.get('metric'))
    if pair is None:
        return None

    this_id = this_detail['id']
    this_ends_at = _parse_iso(this_detail['endsAt'])
    sibling_metric = partner_metric(this_detail['metric'])

    candidates = [
        c for c in competitions
        if c.get('id') != this_id and c.get('endsAt')
        and abs(_parse_iso(c['endsAt']) - this_ends_at) <= SIBLING_TOLERANCE
    ]
    for c in candidates:
        try:
            candidate_detail = await asyncio.to_thread(wom_api.get_competition, c['id'])
        except Exception:
            continue
        if candidate_detail.get('metric') == sibling_metric:
            return candidate_detail
    return None
