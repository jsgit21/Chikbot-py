import asyncio

import discord

from cogs.candyland import candyland_bounty

_THREAD_BODY = (
    '**Tile {tile}**\n'
    'Post your proof images in this thread, then run `/candyland roll` in '
    '<#{channel}>.\n{role}'
)
_ARCHIVE_REASON = 'candyland: tile proven, team advanced'
_CLEAR_REASON = 'candyland: /candyland clear teardown'


def build_team_forum_overwrites(guild, team_role, moderator_role, event_planner_role):
    """Permission overwrites for a team's private forum. @everyone cannot see it;
    the team posts; mods and event planners moderate; the bot has full control."""
    member = discord.PermissionOverwrite(
        view_channel=True, read_message_history=True, send_messages=True,
        send_messages_in_threads=True, create_public_threads=True,
        attach_files=True, embed_links=True, add_reactions=True,
    )
    staff = discord.PermissionOverwrite(
        view_channel=True, read_message_history=True, send_messages=True,
        send_messages_in_threads=True, create_public_threads=True,
        attach_files=True, embed_links=True, add_reactions=True,
        manage_threads=True, manage_messages=True,
    )
    return {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        team_role: member,
        moderator_role: staff,
        event_planner_role: staff,
        guild.me: discord.PermissionOverwrite(
            view_channel=True, read_message_history=True, send_messages=True,
            send_messages_in_threads=True, create_public_threads=True,
            manage_threads=True, manage_messages=True, manage_channels=True,
        ),
    }


async def resolve_channel(bot, channel_id):
    channel = bot.get_channel(channel_id)
    if channel is None:
        channel = await bot.fetch_channel(channel_id)
    return channel


# A tile's proof is always recent (posted since the thread opened); a cap keeps
# /candyland roll inside the interaction window on a chatty thread.
_PROOF_SCAN_LIMIT = 200


async def thread_has_proof_image(bot, thread_id, team_role_id):
    thread = await resolve_channel(bot, thread_id)
    async for message in thread.history(limit=_PROOF_SCAN_LIMIT):
        if not any((a.content_type or '').startswith('image/') for a in message.attachments):
            continue
        member = message.author
        if not isinstance(member, discord.Member):
            try:
                member = await thread.guild.fetch_member(message.author.id)
            except discord.HTTPException:
                continue
        if any(r.id == team_role_id for r in member.roles):
            return True
    return False


async def open_tile_thread(bot, forum_channel_id, mainbingo_channel_id,
                           team_role, tile_sequence):
    forum = await resolve_channel(bot, forum_channel_id)
    body = _THREAD_BODY.format(
        tile=tile_sequence, channel=mainbingo_channel_id, role=team_role.mention
    )
    thread = await forum.create_thread(
        name=f'Tile {tile_sequence}',
        content=body,
        allowed_mentions=discord.AllowedMentions(roles=[team_role]),
    )
    # The pin is cosmetic; a Manage Messages gap must not lose the thread we just
    # created and pinged the team about.
    try:
        starter = await thread.fetch_message(thread.id)
        await starter.pin(reason=_ARCHIVE_REASON)
    except discord.HTTPException:
        pass
    return thread


async def delete_tile_threads(bot, thread_ids):
    """Delete each forum thread by id. Tolerant of a thread that is already
    gone or that the bot cannot delete; never touches the parent forum."""
    deleted, missing, failed = [], [], []
    for thread_id in thread_ids:
        try:
            thread = await resolve_channel(bot, thread_id)
            await thread.delete()
            deleted.append(thread_id)
        except discord.NotFound:
            missing.append(thread_id)
        except discord.HTTPException as e:
            failed.append(f'{thread_id}: {e!r}')
    return {'deleted': deleted, 'missing': missing, 'failed': failed}


async def delete_team_forums(bot, forum_ids):
    """Delete each team forum by id. Tolerant of an already-gone channel; refuses
    anything that is not a ForumChannel. Never touches the parent category."""
    deleted, missing, failed = [], [], []
    for forum_id in forum_ids:
        try:
            channel = await resolve_channel(bot, forum_id)
        except discord.NotFound:
            missing.append(forum_id)
            continue
        if not isinstance(channel, discord.ForumChannel):
            failed.append(f'{forum_id}: not a forum channel ({type(channel).__name__})')
            continue
        try:
            await channel.delete(reason=_CLEAR_REASON)
            deleted.append(forum_id)
        except discord.NotFound:
            missing.append(forum_id)
        except discord.HTTPException as e:
            failed.append(f'{forum_id}: {e!r}')
    return {'deleted': deleted, 'missing': missing, 'failed': failed}


async def delete_team_roles(guild, role_ids, protected_ids):
    """Delete each team role by id. Skips a None id or a protected staff id; refuses
    a managed (integration) role. Tolerant of an already-gone role."""
    deleted, missing, failed = [], [], []
    for role_id in role_ids:
        if role_id is None or role_id in protected_ids:
            continue
        role = guild.get_role(role_id)
        if role is None:
            missing.append(role_id)
            continue
        if role.managed:
            failed.append(f'{role_id}: managed role, refused')
            continue
        try:
            await role.delete(reason=_CLEAR_REASON)
            deleted.append(role_id)
        except discord.NotFound:
            missing.append(role_id)
        except discord.HTTPException as e:
            failed.append(f'{role_id}: {e!r}')
    return {'deleted': deleted, 'missing': missing, 'failed': failed}


async def lock_and_archive(bot, thread_id):
    thread = await resolve_channel(bot, thread_id)
    await thread.edit(archived=True, locked=True, reason=_ARCHIVE_REASON)


async def run_post_roll_ceremony(bot, database, team, team_role,
                                 mainbingo_channel_id, to_sequence,
                                 old_thread_row):
    result = {'steps': {}, 'new_thread_id': None, 'failures': []}

    try:
        new_thread = await open_tile_thread(
            bot, team['forum_channel_id'], mainbingo_channel_id, team_role,
            to_sequence,
        )
        result['new_thread_id'] = new_thread.id
        result['steps']['create_new_thread'] = 'ok'
    except Exception as e:
        result['steps']['create_new_thread'] = 'FAIL'
        result['failures'].append(f'create_new_thread: {e!r}')
        return result  # nothing else is safe to do without the new thread

    try:
        await asyncio.to_thread(
            database.swap_open_thread, team['id'], to_sequence, new_thread.id,
            old_thread_row['id'],
        )
        result['steps']['db_swap_open_thread'] = 'ok'
    except Exception as e:
        result['steps']['db_swap_open_thread'] = 'FAIL'
        result['failures'].append(f'db_swap_open_thread: {e!r}')
        # Leave the old thread usable: it is still the team's open row in the DB,
        # so locking it now would strand them with nowhere to post proof.
        return result

    try:
        await lock_and_archive(bot, old_thread_row['thread_id'])
        result['steps']['archive_old_thread'] = 'ok'
    except Exception as e:
        result['steps']['archive_old_thread'] = 'FAIL'
        result['failures'].append(f'archive_old_thread: {e!r}')

    return result


async def post_bounty_note(bot, thread_id, bounty_key):
    thread = await resolve_channel(bot, thread_id)
    name = candyland_bounty.BOUNTY_NAMES[bounty_key]
    await thread.send(
        f'🎁 This team took the **{name}** bounty against this tile.\n'
        f'{candyland_bounty.BOUNTY_MECHANIC[bounty_key]}'
    )


async def run_bounty_move_ceremony(bot, database, team, team_role,
                                   mainbingo_channel_id, to_sequence,
                                   old_thread_row):
    result = {'steps': {}, 'open_thread_id': None, 'failures': []}

    existing = await asyncio.to_thread(
        database.get_thread_for_tile, team['id'], to_sequence
    )
    try:
        if existing:
            await asyncio.to_thread(
                database.reopen_tile_thread, team['id'], to_sequence,
                old_thread_row['id'],
            )
            thread = await resolve_channel(bot, existing['thread_id'])
            await thread.edit(archived=False, locked=False,
                              reason=_ARCHIVE_REASON)
            result['open_thread_id'] = existing['thread_id']
            result['steps']['reopen_thread'] = 'ok'
        else:
            new_thread = await open_tile_thread(
                bot, team['forum_channel_id'], mainbingo_channel_id, team_role,
                to_sequence,
            )
            await asyncio.to_thread(
                database.swap_open_thread, team['id'], to_sequence,
                new_thread.id, old_thread_row['id'],
            )
            result['open_thread_id'] = new_thread.id
            result['steps']['create_thread'] = 'ok'
    except Exception as e:
        result['steps']['move_thread'] = 'FAIL'
        result['failures'].append(f'move_thread: {e!r}')
        return result  # old thread stays the open row; team can still post

    try:
        await lock_and_archive(bot, old_thread_row['thread_id'])
        result['steps']['archive_old_thread'] = 'ok'
    except Exception as e:
        result['steps']['archive_old_thread'] = 'FAIL'
        result['failures'].append(f'archive_old_thread: {e!r}')

    return result


async def alert_mods(bot, mod_channel_id, team, die, from_sequence, to_sequence,
                     result):
    channel = await resolve_channel(bot, mod_channel_id)
    lines = [
        f'**candyland ceremony fell short** for **{team["name"]}**.',
        f'Roll stands: {die} ({from_sequence} -> {to_sequence}).',
        'Steps: ' + ', '.join(f'{k}={v}' for k, v in result['steps'].items()),
    ]
    if result['new_thread_id']:
        lines.append(f'New thread: <#{result["new_thread_id"]}>')
    for f in result['failures']:
        lines.append(f'- {f}')
    await channel.send('\n'.join(lines))
