"""Vetted WOM metric slugs and display names for BOTW/SOTW.

Sourced from wise-old-man/wise-old-man `server/src/utils/shared/metric.utils.ts`
(SkillProps / BossProps) so slugs and display names match the WOM API exactly.
Only real skills and bosses are offered — WOM's other metric types (activities
like clue scrolls, computed metrics like EHP/EHB) aren't valid BOTW/SOTW targets.
`overall` is excluded from SOTW_METRICS; it's an aggregate, not a trainable skill.
"""

import discord

SOTW_METRICS = {
    'attack': 'Attack',
    'defence': 'Defence',
    'strength': 'Strength',
    'hitpoints': 'Hitpoints',
    'ranged': 'Ranged',
    'prayer': 'Prayer',
    'magic': 'Magic',
    'cooking': 'Cooking',
    'woodcutting': 'Woodcutting',
    'fletching': 'Fletching',
    'fishing': 'Fishing',
    'firemaking': 'Firemaking',
    'crafting': 'Crafting',
    'smithing': 'Smithing',
    'mining': 'Mining',
    'herblore': 'Herblore',
    'agility': 'Agility',
    'thieving': 'Thieving',
    'slayer': 'Slayer',
    'farming': 'Farming',
    'runecrafting': 'Runecrafting',
    'hunter': 'Hunter',
    'construction': 'Construction',
    'sailing': 'Sailing',
}

BOTW_METRICS = {
    'abyssal_sire': 'Abyssal Sire',
    'alchemical_hydra': 'Alchemical Hydra',
    'amoxliatl': 'Amoxliatl',
    'araxxor': 'Araxxor',
    'artio': 'Artio',
    'barrows_chests': 'Barrows Chests',
    'brutus': 'Brutus',
    'bryophyta': 'Bryophyta',
    'callisto': 'Callisto',
    'calvarion': "Calvar'ion",
    'cerberus': 'Cerberus',
    'chambers_of_xeric': 'Chambers Of Xeric',
    'chambers_of_xeric_challenge_mode': 'Chambers Of Xeric (CM)',
    'chaos_elemental': 'Chaos Elemental',
    'chaos_fanatic': 'Chaos Fanatic',
    'commander_zilyana': 'Commander Zilyana',
    'corporeal_beast': 'Corporeal Beast',
    'crazy_archaeologist': 'Crazy Archaeologist',
    'dagannoth_prime': 'Dagannoth Prime',
    'dagannoth_rex': 'Dagannoth Rex',
    'dagannoth_supreme': 'Dagannoth Supreme',
    'deranged_archaeologist': 'Deranged Archaeologist',
    'doom_of_mokhaiotl': 'Doom of Mokhaiotl',
    'duke_sucellus': 'Duke Sucellus',
    'general_graardor': 'General Graardor',
    'giant_mole': 'Giant Mole',
    'grotesque_guardians': 'Grotesque Guardians',
    'hespori': 'Hespori',
    'kalphite_queen': 'Kalphite Queen',
    'king_black_dragon': 'King Black Dragon',
    'kraken': 'Kraken',
    'kreearra': "Kree'Arra",
    'kril_tsutsaroth': "K'ril Tsutsaroth",
    'lunar_chests': 'Lunar Chests',
    'maggot_king': 'Maggot King',
    'mimic': 'Mimic',
    'nex': 'Nex',
    'nightmare': 'Nightmare',
    'phosanis_nightmare': "Phosani's Nightmare",
    'obor': 'Obor',
    'phantom_muspah': 'Phantom Muspah',
    'sarachnis': 'Sarachnis',
    'scorpia': 'Scorpia',
    'scurrius': 'Scurrius',
    'shellbane_gryphon': 'Shellbane Gryphon',
    'skotizo': 'Skotizo',
    'sol_heredit': 'Sol Heredit',
    'spindel': 'Spindel',
    'tempoross': 'Tempoross',
    'the_gauntlet': 'The Gauntlet',
    'the_corrupted_gauntlet': 'The Corrupted Gauntlet',
    'the_hueycoatl': 'The Hueycoatl',
    'the_leviathan': 'The Leviathan',
    'the_royal_titans': 'The Royal Titans',
    'the_whisperer': 'The Whisperer',
    'theatre_of_blood': 'Theatre Of Blood',
    'theatre_of_blood_hard_mode': 'Theatre Of Blood (HM)',
    'thermonuclear_smoke_devil': 'Thermonuclear Smoke Devil',
    'tombs_of_amascut': 'Tombs of Amascut',
    'tombs_of_amascut_expert': 'Tombs of Amascut (Expert Mode)',
    'tzkal_zuk': 'TzKal-Zuk',
    'tztok_jad': 'TzTok-Jad',
    'vardorvis': 'Vardorvis',
    'venenatis': 'Venenatis',
    'vetion': "Vet'ion",
    'vorkath': 'Vorkath',
    'wintertodt': 'Wintertodt',
    'yama': 'Yama',
    'zalcano': 'Zalcano',
    'zulrah': 'Zulrah',
}


def display_name(comp_type, metric_slug):
    """Return the vetted display name for a metric slug, or the raw slug if unknown."""
    metrics = BOTW_METRICS if comp_type == 'botw' else SOTW_METRICS
    return metrics.get(metric_slug, metric_slug)


def _matches(query, metrics):
    query = (query or '').lower()
    choices = [
        discord.OptionChoice(name=name, value=slug)
        for slug, name in metrics.items()
        if query in name.lower() or query in slug
    ]
    choices.sort(key=lambda c: c.name)
    return choices[:25]


async def autocomplete_botw_metric(ctx: discord.AutocompleteContext):
    return _matches(ctx.value, BOTW_METRICS)


async def autocomplete_sotw_metric(ctx: discord.AutocompleteContext):
    return _matches(ctx.value, SOTW_METRICS)
