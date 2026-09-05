import asyncio

import discord

from cogs.candyland import candyland_bounty

_THREAD_BODY = (
    '**Tile {tile}**\n'
    'Post your proof images in this thread, then run `/candyland roll` in '
    '<#{channel}>.\n{role}'
)
_BOUNTY_THREAD_BODY = (
    '**[{label}] bounty**\n'
    'This team took the **{label}** bounty. This means that {task}\n'
    'Post your proof here, then run `/candyland bounty-claim` in <#{channel}>.\n{role}'
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
                           team_role, tile_sequence, bounty_label=None,
                           bounty_task=None):
    forum = await resolve_channel(bot, forum_channel_id)
    if bounty_label:
        name = f'[{bounty_label}] bounty'
        body = _BOUNTY_THREAD_BODY.format(
            label=bounty_label, task=bounty_task,
            channel=mainbingo_channel_id, role=team_role.mention,
        )
    else:
        name = f'Tile {tile_sequence}'
        body = _THREAD_BODY.format(
            tile=tile_sequence, channel=mainbingo_channel_id,
            role=team_role.mention,
        )
    thread = await forum.create_thread(
        name=name,
        content=body,
        allowed_mentions=discord.AllowedMentions(roles=[team_role]),
    )
    # The pin is cosmetic; a Manage Messages gap must not lose the thread we just
    # created and pinged the team about. The outcome is returned (not swallowed)
    # so callers can surface it in the ceremony's result['steps'].
    pin_step = 'ok'
    try:
        starter = await thread.fetch_message(thread.id)
        await starter.pin(reason=_ARCHIVE_REASON)
    except discord.HTTPException as e:
        pin_step = f'FAIL {e!r}'
    return thread, pin_step


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
        new_thread, pin_step = await open_tile_thread(
            bot, team['forum_channel_id'], mainbingo_channel_id, team_role,
            to_sequence,
        )
        result['new_thread_id'] = new_thread.id
        result['steps']['create_new_thread'] = 'ok'
        result['steps']['pin_starter'] = pin_step
        if pin_step != 'ok':
            result['failures'].append(f'pin_starter: {pin_step}')
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


async def post_bounty_note(bot, thread_id, bounty_key, reward):
    thread = await resolve_channel(bot, thread_id)
    name = candyland_bounty.BOUNTY_NAMES[bounty_key]
    await thread.send(
        f'🎁 This team took the **{name}** bounty against this tile.\n'
        f'{reward}'
    )


async def run_bounty_thread_ceremony(bot, database, team, team_role,
                                     mainbingo_channel_id, bounty_key,
                                     bounty_task, to_sequence, old_thread_row):
    # Taking a bounty never moves the team (to_sequence == from_sequence), but
    # every bounty still gets a fresh, labelled tile thread: the bounty task's
    # proof must start from an empty thread, or a stale image left in the old
    # one would satisfy the next roll's proof check for free.
    result = {'steps': {}, 'open_thread_id': None, 'failures': []}
    label = candyland_bounty.BOUNTY_NAMES[bounty_key]

    try:
        new_thread, pin_step = await open_tile_thread(
            bot, team['forum_channel_id'], mainbingo_channel_id, team_role,
            to_sequence, bounty_label=label, bounty_task=bounty_task,
        )
        result['open_thread_id'] = new_thread.id
        result['steps']['create_thread'] = 'ok'
        result['steps']['pin_starter'] = pin_step
        if pin_step != 'ok':
            result['failures'].append(f'pin_starter: {pin_step}')
    except Exception as e:
        result['steps']['create_thread'] = 'FAIL'
        result['failures'].append(f'create_thread: {e!r}')
        return result  # old thread stays the open row; team can still post

    try:
        await asyncio.to_thread(
            database.move_open_thread_to_tile, team['id'], to_sequence,
            new_thread.id,
        )
        result['steps']['db_move_thread'] = 'ok'
    except Exception as e:
        result['steps']['db_move_thread'] = 'FAIL'
        result['failures'].append(f'db_move_thread: {e!r}')
        return result

    try:
        await lock_and_archive(bot, old_thread_row['thread_id'])
        result['steps']['archive_old_thread'] = 'ok'
    except Exception as e:
        result['steps']['archive_old_thread'] = 'FAIL'
        result['failures'].append(f'archive_old_thread: {e!r}')

    return result


async def run_move_thread_ceremony(bot, database, team, team_role,
                                   mainbingo_channel_id, to_sequence,
                                   old_thread_row):
    # Mod /candyland manual-move: open a fresh thread on the target tile, make it
    # the team's single open row, archive the one they were on. old_thread_row is
    # None when the team was already desynced with no open thread - then there is
    # nothing to archive. move_open_thread_to_tile (not swap_open_thread) so a
    # backward move onto a tile the team already has a row for repoints it
    # instead of colliding on the unique key.
    result = {'steps': {}, 'new_thread_id': None, 'failures': []}

    try:
        new_thread, pin_step = await open_tile_thread(
            bot, team['forum_channel_id'], mainbingo_channel_id, team_role,
            to_sequence,
        )
        result['new_thread_id'] = new_thread.id
        result['steps']['create_thread'] = 'ok'
        result['steps']['pin_starter'] = pin_step
        if pin_step != 'ok':
            result['failures'].append(f'pin_starter: {pin_step}')
    except Exception as e:
        result['steps']['create_thread'] = 'FAIL'
        result['failures'].append(f'create_thread: {e!r}')
        return result

    try:
        await asyncio.to_thread(
            database.move_open_thread_to_tile, team['id'], to_sequence,
            new_thread.id,
        )
        result['steps']['db_move_thread'] = 'ok'
    except Exception as e:
        result['steps']['db_move_thread'] = 'FAIL'
        result['failures'].append(f'db_move_thread: {e!r}')
        return result

    if old_thread_row is not None:
        try:
            await lock_and_archive(bot, old_thread_row['thread_id'])
            result['steps']['archive_old_thread'] = 'ok'
        except Exception as e:
            result['steps']['archive_old_thread'] = 'FAIL'
            result['failures'].append(f'archive_old_thread: {e!r}')

    return result


async def run_reveal_ceremony(bot, mainbingo_channel_id, leader_thread_id,
                              team_role):
    # /candyland doomsday: the public reveal line in #mainbingo plus a ping in
    # the leader's existing tile thread. No thread is opened or archived - the
    # leader keeps its thread (and its proof image) until it rolls.
    result = {'steps': {}, 'new_thread_id': None, 'failures': []}

    try:
        channel = await resolve_channel(bot, mainbingo_channel_id)
        await channel.send(
            'Yama has a new contract. The road did not end where you thought '
            'it did.',
            allowed_mentions=discord.AllowedMentions.none(),
        )
        result['steps']['mainbingo_line'] = 'ok'
    except Exception as e:
        result['steps']['mainbingo_line'] = 'FAIL'
        result['failures'].append(f'mainbingo_line: {e!r}')

    if leader_thread_id is None:
        return result

    try:
        thread = await resolve_channel(bot, leader_thread_id)
        await thread.send(
            f'{team_role.mention} the road did not end where you thought it '
            f'did. Roll when you are ready.',
            allowed_mentions=discord.AllowedMentions(roles=[team_role]),
        )
        result['steps']['leader_ping'] = 'ok'
    except Exception as e:
        result['steps']['leader_ping'] = 'FAIL'
        result['failures'].append(f'leader_ping: {e!r}')

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
