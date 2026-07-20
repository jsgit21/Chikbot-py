"""Registry of BOTW/SOTW competition-type behavior, keyed by the same string
the WOM title is inferred into. Adding a third type is one new TYPES entry
plus one new env var, no migration.
"""

import dataclasses
import datetime


@dataclasses.dataclass(frozen=True)
class CompetitionType:
    key: str
    display_name: str
    title_keywords: list[str]
    title_label: str
    gained_unit: str | None = None
    winner_role_env: str | None = None
    feeds_nominator_for: str | None = None
    nudge_cadence_weeks: int | None = None
    creatable: bool = True
    results_enabled: bool = True
    result_template: str | None = None
    nudge_seed_last_ended: datetime.date | None = None


TYPES = {
    'botw': CompetitionType(
        key='botw',
        display_name='BOTW',
        gained_unit='KC',
        winner_role_env='BOTW_WINNER_ROLE',
        title_keywords=['boss of the week', 'botw'],
        title_label='Boss of the Week',
        feeds_nominator_for='sotw',
        result_template=(
            '{mention} with **{label}** (`{rsn}`)\n\n'
            "Congrats! Your pick decides next cycle's {next_target} target."
        ),
    ),
    'sotw': CompetitionType(
        key='sotw',
        display_name='SOTW',
        gained_unit='XP',
        winner_role_env='SOTW_WINNER_ROLE',
        title_keywords=['skill of the week'],
        title_label='Skill of the Week',
        feeds_nominator_for='botw',
        result_template=(
            '{mention} with **{label}** (`{rsn}`)\n\n'
            "Congrats! Your pick decides next cycle's {next_target} target."
        ),
    ),
    'boss_rush': CompetitionType(
        key='boss_rush',
        display_name='Boss Rush',
        # not detectable from a title yet -- likely 'boss rush' once this type is live
        title_keywords=[],
        title_label='Boss Rush',
        nudge_cadence_weeks=None,  # run as-needed, never nudge
        creatable=False,
        results_enabled=False,
    ),
    'skill_challenge': CompetitionType(
        key='skill_challenge',
        display_name='Skill Challenge',
        # not detectable from a title yet -- likely 'skill challenge' once this type is live
        title_keywords=[],
        title_label='Skill Challenge',
        nudge_cadence_weeks=None,  # run as-needed, never nudge
        creatable=False,
        results_enabled=False,
    ),
    'lucky_learner': CompetitionType(
        key='lucky_learner',
        display_name='Lucky Learner',
        title_keywords=['[lucky]'],
        title_label='Lucky Learner',
        nudge_cadence_weeks=13,  # roughly quarterly
        creatable=False,
        results_enabled=False,
        # One-time backfill -- remove once _check_standalone_cadence_nudges has organically
        # found at least one real WOM-detected '[lucky]' competition and no longer needs this.
        nudge_seed_last_ended=datetime.date(2026, 4, 14),  # last Lucky Duck event, Q2 2026
    ),
    'bingo': CompetitionType(
        key='bingo',
        display_name='Bingo',
        title_keywords=['[bingo]'],
        title_label='Bingo',
        nudge_cadence_weeks=26,  # roughly twice a year
        creatable=False,
        results_enabled=False,
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
