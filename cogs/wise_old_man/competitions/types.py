"""Registry of BOTW/SOTW competition-type behavior, keyed by the same string
the WOM title is inferred into. Adding a third type is one new TYPES entry
plus one new env var, no migration.
"""

import dataclasses


@dataclasses.dataclass(frozen=True)
class CompetitionType:
    key: str
    display_name: str
    gained_unit: str
    winner_role_env: str
    title_keywords: list[str]
    title_label: str
    feeds_nominator_for: str


TYPES = {
    'botw': CompetitionType(
        key='botw',
        display_name='BOTW',
        gained_unit='KC',
        winner_role_env='BOTW_WINNER_ROLE',
        title_keywords=['boss of the week'],
        title_label='Boss of the Week',
        feeds_nominator_for='sotw',
    ),
    'sotw': CompetitionType(
        key='sotw',
        display_name='SOTW',
        gained_unit='XP',
        winner_role_env='SOTW_WINNER_ROLE',
        title_keywords=['skill of the week'],
        title_label='Skill of the Week',
        feeds_nominator_for='botw',
    ),
}


def infer_type_from_title(title):
    """Return the CompetitionType whose title_keywords match, or None."""
    lowered = (title or '').lower()
    for comp_type in TYPES.values():
        if any(keyword in lowered for keyword in comp_type.title_keywords):
            return comp_type
    return None


def nominator_source_for(comp_type_key):
    """The type whose winner feeds this type's next nominator (reverse lookup
    over feeds_nominator_for — there are only two types today, so this is a
    simple linear scan, not a dict).
    """
    for comp_type in TYPES.values():
        if comp_type.feeds_nominator_for == comp_type_key:
            return comp_type
    return None
