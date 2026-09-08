"""TEST HARNESS - remove after the 2026-09 event.

Stands up and tears down a disposable Candyland test environment so the full
flow can be played in #mainbingo without hand-building channels and roles. The
/candyland test-setup and /candyland test-teardown command shims live in
candyland_cog.py under a TEST HARNESS banner; every line of logic is here.

Removal after the event: delete this file, delete the bannered TEST HARNESS
block in candyland_cog.py, delete the mod-guide test section.

Imports and calls production helpers (candyland_ceremony, candyland_db_methods,
candyland_connection); does NOT import candyland_cog (which imports this), so
there is no circular import.
"""

import asyncio

import discord

from . import candyland_ceremony
from . import candyland_connection
from . import candyland_db_methods as database

TEST_EVENT_SLUG = 'candyland-test'
TEST_CATEGORY_NAME = 'Candyland Test'
TEST_FORUM_PREFIX = 'candyland-test-'
TEST_ROLE_PREFIX = 'Candyland Test '

# Names for up to the cap of 4 teams.
_TEAM_NAMES = ['Alpha', 'Bravo', 'Charlie', 'Delta']
MAX_TEAMS = 4
DEFAULT_TEAMS = 2

_REASON = 'candyland test harness'

# Hard denylist: real event objects teardown must never delete, even if a name
# or prefix somehow matched. Real team roles are chikbot-created per event now
# (their ids are not known here), so they are covered by the name-prefix fence,
# not this list. run_teardown also adds MODERATOR_ROLE / EVENT_PLANNER_ROLE.
PROTECTED_IDS = frozenset({
    1543654850271912037,   # #mainbingo
    1535394096129118278,   # Fall 2026 Bingo category
})


def _clamp_team_count(raw):
    return max(1, min(raw, MAX_TEAMS))


def _summarize(pairs):
    created = [name for name, status in pairs if status == 'created']
    adopted = [name for name, status in pairs if status == 'adopted']
    parts = []
    if created:
        parts.append('created ' + ', '.join(created))
    if adopted:
        parts.append('adopted ' + ', '.join(adopted))
    return '; '.join(parts) if parts else 'none'


async def run_setup(cog, ctx, teams_raw, tester2):
    moderator_role = ctx.guild.get_role(cog.moderator_role_id)
    event_planner_role = ctx.guild.get_role(cog.event_planner_role_id)
    if moderator_role is None or event_planner_role is None:
        await ctx.respond(
            'Could not resolve MODERATOR_ROLE / EVENT_PLANNER_ROLE.',
            ephemeral=True,
        )
        return

    await ctx.defer()
    team_count = _clamp_team_count(teams_raw)

    roles_built, forums_built, teams_built, threads_built = [], [], [], []

    category = discord.utils.get(ctx.guild.categories, name=TEST_CATEGORY_NAME)
    if category is None:
        category = await ctx.guild.create_category(TEST_CATEGORY_NAME, reason=_REASON)
        category_status = 'created'
    else:
        category_status = 'adopted'

    slots = []
    for i in range(team_count):
        name = _TEAM_NAMES[i]
        role_name = f'{TEST_ROLE_PREFIX}{name}'
        forum_name = f'{TEST_FORUM_PREFIX}{name.lower()}'

        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role is None:
            role = await ctx.guild.create_role(
                name=role_name, mentionable=True, reason=_REASON
            )
            roles_built.append((name, 'created'))
        else:
            roles_built.append((name, 'adopted'))

        forum = discord.utils.get(category.channels, name=forum_name)
        if forum is None:
            forum = await ctx.guild.create_forum_channel(
                name=forum_name, category=category,
                overwrites=candyland_ceremony.build_team_forum_overwrites(
                    ctx.guild, role, moderator_role, event_planner_role
                ),
                reason=_REASON,
            )
            forums_built.append((name, 'created'))
        else:
            forums_built.append((name, 'adopted'))

        for member in (ctx.author, tester2):
            if member is not None and role not in member.roles:
                await member.add_roles(role, reason=_REASON)

        slots.append({'name': name, 'sort_order': i, 'role': role, 'forum': forum})

    event = await asyncio.to_thread(database.get_event, TEST_EVENT_SLUG)
    if event is None:
        await asyncio.to_thread(database.create_event, TEST_EVENT_SLUG, None, None)
        event = await asyncio.to_thread(database.get_event, TEST_EVENT_SLUG)
        event_status = 'created'
    else:
        event_status = 'adopted'

    existing_role_ids = {
        t['role_id'] for t in await asyncio.to_thread(database.get_teams, event['id'])
    }
    for slot in slots:
        if slot['role'].id in existing_role_ids:
            teams_built.append((slot['name'], 'adopted'))
            continue
        await asyncio.to_thread(
            database.register_team, event['id'],
            f'{TEST_ROLE_PREFIX}{slot["name"]}', slot['role'].id,
            slot['forum'].id, slot['sort_order'],
        )
        teams_built.append((slot['name'], 'created'))

    role_by_id = {slot['role'].id: slot['role'] for slot in slots}
    for team in await asyncio.to_thread(database.get_teams, event['id']):
        role = role_by_id.get(team['role_id'])
        if role is None:
            continue
        if await asyncio.to_thread(database.get_any_thread, team['id']) is not None:
            threads_built.append((team['name'], 'adopted'))
            continue
        thread, _pin_step = await candyland_ceremony.open_tile_thread(
            cog.bot, team['forum_channel_id'], cog.mainbingo_channel_id, role, 1
        )
        await asyncio.to_thread(database.open_tile_thread, team['id'], 1, thread.id)
        threads_built.append((team['name'], 'created'))

    await asyncio.to_thread(database.set_event_status, TEST_EVENT_SLUG, 'live')

    lines = [f'**Candyland test environment** ({team_count} team(s)):']
    if teams_raw != team_count:
        lines.append(f'Requested {teams_raw} team(s), clamped to {team_count}.')
    lines.append(f'- Category `{TEST_CATEGORY_NAME}`: {category_status}')
    lines.append(f'- Roles: {_summarize(roles_built)}')
    lines.append(f'- Forums: {_summarize(forums_built)}')
    lines.append(f'- Event `{TEST_EVENT_SLUG}`: {event_status}')
    lines.append(f'- Team rows: {_summarize(teams_built)}')
    lines.append(f'- Tile-1 threads: {_summarize(threads_built)}')
    lines.append(f'Event is **live**. Roll in <#{cog.mainbingo_channel_id}>.')
    await ctx.respond('\n'.join(lines))


async def run_teardown(cog, ctx):
    await ctx.defer()
    protected = PROTECTED_IDS | {cog.moderator_role_id, cog.event_planner_role_id}

    threads = {'deleted': [], 'missing': [], 'failed': []}
    forums = {'deleted': [], 'missing': [], 'failed': []}
    roles = {'deleted': [], 'missing': [], 'failed': []}
    swept_channels, swept_roles, sweep_failures = [], [], []

    event = await asyncio.to_thread(database.get_event, TEST_EVENT_SLUG)
    if event is not None:
        teams = await asyncio.to_thread(database.get_teams, event['id'])
        thread_rows = await asyncio.to_thread(
            database.get_all_tile_threads, event['id']
        )
        threads = await candyland_ceremony.delete_tile_threads(
            cog.bot, [r['thread_id'] for r in thread_rows]
        )
        forums = await candyland_ceremony.delete_team_forums(
            cog.bot, [t['forum_channel_id'] for t in teams]
        )
        roles = await candyland_ceremony.delete_team_roles(
            ctx.guild, [t['role_id'] for t in teams], protected
        )
        await asyncio.to_thread(database.clear_event_teams, event['id'])
        await asyncio.to_thread(_delete_test_event)

    category = discord.utils.get(ctx.guild.categories, name=TEST_CATEGORY_NAME)
    if category is not None:
        for channel in list(category.channels):
            if not channel.name.startswith(TEST_FORUM_PREFIX) or channel.id in protected:
                continue
            try:
                await channel.delete(reason=_REASON)
                swept_channels.append(channel.name)
            except (discord.NotFound, discord.HTTPException) as e:
                sweep_failures.append(f'{channel.name}: {e!r}')

    for role in list(ctx.guild.roles):
        if not role.name.startswith(TEST_ROLE_PREFIX):
            continue
        if role.managed or role.id in protected:
            continue
        try:
            await role.delete(reason=_REASON)
            swept_roles.append(role.name)
        except (discord.NotFound, discord.HTTPException) as e:
            sweep_failures.append(f'{role.name}: {e!r}')

    category_removed = False
    if category is not None and category.id not in protected and not category.channels:
        try:
            await category.delete(reason=_REASON)
            category_removed = True
        except (discord.NotFound, discord.HTTPException) as e:
            sweep_failures.append(f'{category.name}: {e!r}')

    lines = ['**Candyland test environment teardown**']
    if event is not None:
        lines.append(
            f'- Cleared `{TEST_EVENT_SLUG}`: {len(threads["deleted"])} thread(s), '
            f'{len(forums["deleted"])} forum(s), {len(roles["deleted"])} role(s) deleted; '
            f'{len(threads["missing"])}/{len(forums["missing"])}/{len(roles["missing"])} '
            f'thread/forum/role already gone. Event row deleted.'
        )
    else:
        lines.append(f'- No `{TEST_EVENT_SLUG}` event row to clear.')
    if swept_channels:
        lines.append('- Swept leftover channels: ' + ', '.join(swept_channels))
    if swept_roles:
        lines.append('- Swept leftover roles: ' + ', '.join(swept_roles))
    lines.append(
        f'- Category `{TEST_CATEGORY_NAME}`: '
        + ('deleted' if category_removed else 'left in place' if category is not None
           else 'already gone')
    )
    failed = threads['failed'] + forums['failed'] + roles['failed'] + sweep_failures
    if failed:
        lines.append('- Could not delete: ' + '; '.join(failed))
    if event is None and not swept_channels and not swept_roles and category is None:
        lines.append('Nothing to remove.')
    lines.append('`#mainbingo` and the real team roles are untouched.')
    await ctx.respond('\n'.join(lines))


def _delete_test_event():
    # The one DB write teardown needs that no production helper covers. Raw SQL,
    # autocommit on (repo default per candyland_connection). Cascades to
    # team / tile_thread / movement / team_state / bounty_use.
    db = candyland_connection.create_connection()
    db.cursor().execute(
        "delete from event where slug = %s", (TEST_EVENT_SLUG,)
    )
