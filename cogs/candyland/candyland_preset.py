"""EVENT PRESET - remove after the 2026-09 event.

One-shot setup for the real Casual GMers Land event: /candyland setup-event
plus three /candyland team-add calls, collapsed into a single livestream-
friendly command with this event's fixed roster (team names, acronyms,
colours, captains) baked in. The /candyland setup-gmers-land command shim
lives in candyland_cog.py under an EVENT PRESET banner; every line of logic
is here.

Removal after the event: delete this file, delete the bannered EVENT PRESET
block in candyland_cog.py, delete the mod-guide section documenting this
command.

Imports and calls production helpers (candyland_ceremony,
candyland_db_methods); does NOT import candyland_cog (which imports this), so
there is no circular import.
"""

import asyncio

import discord

from . import candyland_ceremony
from . import candyland_db_methods as database

EVENT_SLUG = 'casual-gmers-land'

TEAMS = (
    {'name': "Bird's Bodacious Cloggers", 'acronym': 'BBC',
     'colour': 0xCCCCFF, 'captain_id': 168204366308835329, 'sort_order': 0},
    {'name': 'Goofy Goober Gang', 'acronym': 'GGG',
     'colour': 0x00A4FF, 'captain_id': 119829827753607170, 'sort_order': 1},
    {'name': "Yargle's Elite Sweats", 'acronym': 'YES',
     'colour': 0x13692A, 'captain_id': 270768673784987649, 'sort_order': 2},
)

_REASON = 'candyland: setup-gmers-land'


async def _resolve_emoji(emojis_by_name, acronym, warnings):
    """The team's custom server emoji, as (icon_bytes, markup) - markup is the
    ready-to-use <:name:id> string stored on the team row and later swapped in
    for the dice emoji in roll messages. Either element is None (with a
    warning) if there is no matching emoji, or the role icon alone failed to
    read - a missing icon must not abort a team."""
    emoji = emojis_by_name.get(acronym.upper())
    if emoji is None:
        warnings.append(
            f'{acronym}: no server emoji named `{acronym}` - role created '
            f'without an icon, roll messages will use the dice emoji.'
        )
        return None, None
    markup = str(emoji)
    try:
        return await emoji.read(), markup
    except discord.HTTPException as e:
        warnings.append(
            f'{acronym}: could not read emoji `{acronym}` for the role icon: `{e!r}`.'
        )
        return None, markup


def _colour_winner(existing_roles, team_role):
    """Which role, among a member's existing coloured roles plus the newly
    assigned team role, wins Discord's display-colour precedence (highest
    position among roles that have a colour set)."""
    candidates = [r for r in existing_roles if r.colour.value != 0] + [team_role]
    return max(candidates, key=lambda r: r.position)


async def run_setup(cog, ctx):
    event = await asyncio.to_thread(database.get_event, EVENT_SLUG)
    if event is not None:
        await ctx.respond(
            f'**{EVENT_SLUG}** already exists (status `{event["status"]}`). '
            f'`/candyland delete event_slug:{EVENT_SLUG}` first if you need to '
            f'redo this.'
        )
        return

    category = ctx.guild.get_channel(cog.candyland_category_id)
    if not isinstance(category, discord.CategoryChannel):
        await ctx.respond(
            f'CANDYLAND_CATEGORY (`{cog.candyland_category_id}`) is not a category '
            f'channel in this guild. Check the env var.'
        )
        return
    moderator_role = ctx.guild.get_role(cog.moderator_role_id)
    event_planner_role = ctx.guild.get_role(cog.event_planner_role_id)
    if moderator_role is None or event_planner_role is None:
        await ctx.respond(
            'Could not resolve the Moderator or Event Planner role from env - '
            'not creating anything. Check MODERATOR_ROLE / EVENT_PLANNER_ROLE.'
        )
        return

    await ctx.defer()

    warnings = []
    emojis_by_name = {e.name.upper(): e for e in await ctx.guild.fetch_emojis()}

    event_id = await asyncio.to_thread(
        database.create_event, EVENT_SLUG, None, None
    )

    team_lines = []
    for team in TEAMS:
        icon, emoji_markup = await _resolve_emoji(
            emojis_by_name, team['acronym'], warnings
        )

        try:
            built = await candyland_ceremony.provision_team(
                ctx.guild, category, moderator_role, event_planner_role,
                _REASON, EVENT_SLUG, team['name'], team['acronym'],
                colour=team['colour'], icon=icon,
            )
        except discord.HTTPException as e:
            team_lines.append(
                f"- **{team['name']}**: FAILED to create role/channels: `{e!r}`"
            )
            continue

        role = built['role']
        team_id = await asyncio.to_thread(
            database.register_team, event_id, team['name'], role.id,
            built['forum'].id, team['sort_order'], acronym=team['acronym'],
            voice_channel_id=built['voice'].id, chat_channel_id=built['chat'].id,
            emoji=emoji_markup,
        )

        captain_status = 'not attempted'
        member = None
        try:
            member = await ctx.guild.fetch_member(team['captain_id'])
        except discord.HTTPException as e:
            captain_status = f'FAILED to look up captain: `{e!r}`'

        if member is not None:
            existing_roles = member.roles[1:]  # drop @everyone
            try:
                await member.add_roles(role, reason=_REASON)
            except discord.HTTPException as e:
                captain_status = f'FAILED to assign to {member.mention}: `{e!r}`'
            else:
                captain_status = f'assigned to {member.mention}'
                winner = _colour_winner(existing_roles, role)
                if winner.id != role.id:
                    warnings.append(
                        f"{team['acronym']}: {member.mention} already holds "
                        f'**{winner.name}**, which outranks the team colour - '
                        f'move **{role.name}** above it if that matters.'
                    )

        team_lines.append(
            f"- **{team['name']}** (`{team['acronym']}`, id `{team_id}`): "
            f'role <@&{role.id}> at position {role.position}  ·  '
            f'icon {"ok" if icon else "skipped"}  ·  '
            f'roll emoji {"ok" if emoji_markup else "skipped (dice fallback)"}  ·  '
            f'captain {captain_status}'
        )

    await asyncio.to_thread(
        database.write_audit, ctx.author.id, 'setup-gmers-land',
        {'event_slug': EVENT_SLUG, 'event_id': event_id, 'warnings': warnings},
    )

    lines = [f'**Casual GMers Land** event created (`{EVENT_SLUG}`, id `{event_id}`).']
    lines.extend(team_lines)
    if warnings:
        lines.append('')
        lines.append('**Warnings:**')
        lines.extend(f'- {w}' for w in warnings)
    lines.append('')
    lines.append(f'Run `/candyland start event_slug:{EVENT_SLUG}` when the draft is done.')
    await ctx.respond(
        '\n'.join(lines), allowed_mentions=discord.AllowedMentions.none(),
    )
