import asyncio

import discord

_THREAD_BODY = (
    '**Tile {tile}** - goal text lands in Phase F.\n'
    'Post your proof images in this thread, then run `/candyland roll` in '
    '<#{channel}>.\n{role}'
)
_ARCHIVE_REASON = 'candyland: tile proven, team advanced'


async def resolve_channel(bot, channel_id):
    channel = bot.get_channel(channel_id)
    if channel is None:
        channel = await bot.fetch_channel(channel_id)
    return channel


async def thread_has_proof_image(bot, thread_id, team_role_id):
    thread = await resolve_channel(bot, thread_id)
    async for message in thread.history(limit=None):
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


async def lock_and_archive(bot, thread_id):
    thread = await resolve_channel(bot, thread_id)
    await thread.edit(archived=True, locked=True, reason=_ARCHIVE_REASON)


async def database_open_and_close(database, team_id, tile_sequence,
                                  new_thread_id, old_thread_row_id):
    def _work():
        database.open_tile_thread(team_id, tile_sequence, new_thread_id)
        database.close_tile_thread(old_thread_row_id)
    await asyncio.to_thread(_work)


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
        await database_open_and_close(database, team['id'],
                                      to_sequence, new_thread.id, old_thread_row['id'])
        result['steps']['db_swap_open_thread'] = 'ok'
    except Exception as e:
        result['steps']['db_swap_open_thread'] = 'FAIL'
        result['failures'].append(f'db_swap_open_thread: {e!r}')

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
