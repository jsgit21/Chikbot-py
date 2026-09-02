"""Casual GMers Land (candyland) cog.

Phase A: the schema in database/SCHEMA.sql, the DB-access module
candyland_db_methods.py, and the mod-gated admin commands to create an event,
register teams, and read board state back.

Phase B: /candyland start (group kick-off, opens every team's tile-1 forum
thread), /candyland roll (1d4+1 movement in #mainbingo plus the per-tile forum
ceremony, the movement writes and the state fold), and /candyland clear (reset a
test event). /candyland team-add provisions the team's Discord role and locked
forum itself; /candyland clear deletes that event's roles, forums and tile
threads and drops its team rows.

Phase C wave 1: /candyland bounty (take one of six bounties against the current
  tile instead of rolling; once per bounty per board, tracked in
  candyland.bounty_use) and /candyland bounties (list your team's pool, used
  ones struck through). Phase C waves 2-3 (not here): the doomsday reveal, the
  board-1->2 transition, a thread-repair command, /candyland end.
"""

import asyncio
import os

import discord
from discord.ext import commands

from . import candyland_board
from . import candyland_bounty
from . import candyland_ceremony
from . import candyland_roll
from . import candyland_db_methods as database
from cogs.roll_dice import dice_art


async def is_moderator(ctx):
    mod_role = discord.utils.get(ctx.author.roles, name='Moderator', id=360455451852406797)
    return mod_role is not None


class Candyland(commands.Cog):

    candyland = discord.SlashCommandGroup('candyland', 'Casual GMers Land event admin')

    _ROLL_REFUSALS = {
        candyland_roll.NO_TEAM: 'You are not on a team for this event.',
        candyland_roll.MULTI_TEAM: 'You hold more than one team role.',
        candyland_roll.OUT_OF_SYNC: (
            "Your team's tile thread is out of sync with the board; a mod needs "
            'to repair it.'
        ),
        candyland_roll.FINAL_TILE: (
            'Your team is on the final tile. After you complete it, a moderator '
            'will handle finalization.'
        ),
    }

    _BOUNTY_REFUSALS = {
        candyland_roll.NO_TEAM: 'You are not on a team for this event.',
        candyland_roll.MULTI_TEAM: 'You hold more than one team role.',
        candyland_roll.OUT_OF_SYNC: (
            "Your team's tile thread is out of sync with the board; a mod needs "
            'to repair it.'
        ),
    }

    def __init__(self, bot):
        self.bot = bot
        self.mainbingo_channel_id = int(os.getenv('MAINBINGO_CHANNEL'))
        self.moderator_channel_id = int(os.getenv('MODERATOR_CHANNEL'))
        self.candyland_category_id = int(os.getenv('CANDYLAND_CATEGORY'))
        self.event_planner_role_id = int(os.getenv('EVENT_PLANNER_ROLE'))
        self.moderator_role_id = int(os.getenv('MODERATOR_ROLE'))

    @commands.check(is_moderator)
    @candyland.command(name='setup-event', description='Create a candyland event')
    async def setup_event(self, ctx,
                          slug: discord.Option(str, 'Unique event slug'),
                          starts_at: discord.Option(str, 'Start time, ISO-8601 UTC', required=False, default=None),
                          ends_at: discord.Option(str, 'End time, ISO-8601 UTC', required=False, default=None)):
        event_id = await asyncio.to_thread(
            database.create_event, slug, starts_at, ends_at
        )
        await asyncio.to_thread(
            database.write_audit, ctx.author.id, 'setup-event',
            {'slug': slug, 'event_id': event_id}
        )
        await ctx.respond(f'Created candyland event **{slug}** (id `{event_id}`).')

    @commands.check(is_moderator)
    @candyland.command(name='team-add', description='Register a team for a candyland event')
    async def team_add(self, ctx,
                       event_slug: discord.Option(str, 'Event slug'),
                       team_name: discord.Option(str, 'Team name (also the role name)'),
                       acronym: discord.Option(str, 'Short tag for the forum channel name'),
                       sort_order: discord.Option(int, 'Display order', default=0)):
        event = await asyncio.to_thread(database.get_event, event_slug)
        if event is None:
            await ctx.respond(f'No candyland event with slug **{event_slug}**.')
            return
        if event['status'] != 'setup':
            await ctx.respond(
                f'Event **{event_slug}** is **{event["status"]}**, not `setup`. '
                f'Add every team before `/candyland start`.'
            )
            return

        teams = await asyncio.to_thread(database.get_teams, event['id'])
        if any(t['name'].casefold() == team_name.casefold() for t in teams):
            await ctx.respond(f'Team **{team_name}** already exists for **{event_slug}**.')
            return

        category = ctx.guild.get_channel(self.candyland_category_id)
        if not isinstance(category, discord.CategoryChannel):
            await ctx.respond(
                f'CANDYLAND_CATEGORY (`{self.candyland_category_id}`) is not a category '
                f'channel in this guild. Check the env var.'
            )
            return
        moderator_role = ctx.guild.get_role(self.moderator_role_id)
        event_planner_role = ctx.guild.get_role(self.event_planner_role_id)
        if moderator_role is None or event_planner_role is None:
            await ctx.respond(
                'Could not resolve the Moderator or Event Planner role from env - '
                'not creating anything. Check MODERATOR_ROLE / EVENT_PLANNER_ROLE.'
            )
            return

        await ctx.defer()

        reason = f'candyland {event_slug}: team {team_name}'
        role = await ctx.guild.create_role(name=team_name, mentionable=True, reason=reason)
        overwrites = candyland_ceremony.build_team_forum_overwrites(
            ctx.guild, role, moderator_role, event_planner_role
        )
        try:
            forum = await ctx.guild.create_forum_channel(
                name=acronym, category=category, overwrites=overwrites, reason=reason
            )
        except discord.HTTPException as e:
            await role.delete(reason=f'{reason}: forum create failed, rolling back')
            await ctx.respond(
                f'Could not create the forum channel: `{e!r}`. '
                f'Rolled back the **{team_name}** role.'
            )
            return

        team_id = await asyncio.to_thread(
            database.register_team, event['id'], team_name, role.id, forum.id, sort_order
        )
        await asyncio.to_thread(
            database.write_audit, ctx.author.id, 'team-add',
            {'event_slug': event_slug, 'name': team_name, 'acronym': acronym,
             'role_id': role.id, 'forum_channel_id': forum.id, 'team_id': team_id},
        )
        await ctx.respond(
            f'Registered team **{team_name}** (id `{team_id}`) for **{event_slug}**.\n'
            f'Role: <@&{role.id}>  ·  Forum: <#{forum.id}>\n'
            f'Assign the role to this team\'s members - chikbot does not know who they are.',
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @commands.check(is_moderator)
    @candyland.command(name='status', description='Show board state for a candyland event')
    async def status(self, ctx,
                     event_slug: discord.Option(str, 'Event slug')):
        event = await asyncio.to_thread(database.get_event, event_slug)
        if event is None:
            await ctx.respond(f'No candyland event with slug **{event_slug}**.')
            return

        rows = await asyncio.to_thread(database.get_all_state, event['id'])
        await asyncio.to_thread(
            database.write_audit, ctx.author.id, 'status', {'event_slug': event_slug}
        )

        if not rows:
            await ctx.respond(f'**{event_slug}** has no teams yet.')
            return

        lines = [f"__Board state for **{event_slug}**__"]
        for row in rows:
            lines.append(
                f'- **{row["name"]}**: tile {row["current_sequence"]} '
                f'(updated {row["updated_at"]})'
            )
        await ctx.respond('\n'.join(lines))

    @commands.check(is_moderator)
    @candyland.command(name='start', description="Open every team's tile-1 thread and start the event")
    async def start(self, ctx,
                    event_slug: discord.Option(str, 'Event slug')):
        event = await asyncio.to_thread(database.get_event, event_slug)
        if event is None:
            await ctx.respond(f'No candyland event with slug **{event_slug}**.')
            return
        if event['status'] == 'ended':
            await ctx.respond(f'**{event_slug}** has already ended.')
            return

        await ctx.defer()

        await asyncio.to_thread(database.set_event_status, event_slug, 'live')
        teams = await asyncio.to_thread(database.get_teams, event['id'])

        opened, skipped, failed = [], [], []
        for team in teams:
            # Idempotency: a team that has ever had a tile thread has already
            # been kicked off. Re-running start must not open a second tile-1
            # thread (it would collide on the (team_id, tile_sequence) key, and
            # for an advanced team it would strand them out of sync).
            existing = await asyncio.to_thread(database.get_any_thread, team['id'])
            if existing is not None:
                skipped.append(team['name'])
                continue
            team_role = ctx.guild.get_role(team['role_id'])
            if team_role is None:
                failed.append(f'{team["name"]}: role {team["role_id"]} not found')
                continue
            try:
                thread = await candyland_ceremony.open_tile_thread(
                    self.bot, team['forum_channel_id'], self.mainbingo_channel_id,
                    team_role, 1,
                )
                await asyncio.to_thread(
                    database.open_tile_thread, team['id'], 1, thread.id
                )
                opened.append(team['name'])
            except Exception as e:
                failed.append(f'{team["name"]}: {e!r}')

        await asyncio.to_thread(
            database.write_audit, ctx.author.id, 'start',
            {'event_slug': event_slug, 'opened': opened, 'skipped': skipped, 'failed': failed},
        )

        lines = [f'**{event_slug}** is live.']
        if opened:
            lines.append('Opened: ' + ', '.join(opened))
        if skipped:
            lines.append('Skipped (already started): ' + ', '.join(skipped))
        if failed:
            lines.append('Failed: ' + '; '.join(failed))
        await ctx.respond('\n'.join(lines))

    @candyland.command(name='roll', description="Roll your team's move in Casual GMers Land")
    async def roll(self, ctx):
        if ctx.channel.id != self.mainbingo_channel_id:
            await ctx.respond(
                f'`/candyland roll` only works in <#{self.mainbingo_channel_id}>.',
                ephemeral=True,
            )
            return

        # thread_has_proof_image below scans thread history over HTTP, so defer
        # up front to keep the interaction alive; pre-roll refusals go out as
        # ephemeral followups and the public roll result is a channel message.
        await ctx.defer(ephemeral=True)

        event = await asyncio.to_thread(database.get_active_event)
        if event is None:
            await ctx.followup.send(
                'No live event - ask a mod to run `/candyland start`.', ephemeral=True
            )
            return

        teams = await asyncio.to_thread(database.get_teams, event['id'])
        caller_role_ids = {r.id for r in ctx.author.roles}
        team, refusal = candyland_roll.resolve_caller_team(teams, caller_role_ids)
        if refusal is not None:
            await ctx.followup.send(self._ROLL_REFUSALS[refusal], ephemeral=True)
            return

        thread_row = await asyncio.to_thread(database.get_open_thread, team['id'])
        if thread_row is None:
            await ctx.followup.send(
                'No active tile - has the event started? Ask a mod to run `/candyland start`.',
                ephemeral=True,
            )
            return

        state = await asyncio.to_thread(database.get_team_state, team['id'])
        from_sequence = state['current_sequence']
        board_size = candyland_board.BOARD1_SIZE

        blocked = candyland_roll.blocking_condition(
            thread_row['tile_sequence'], from_sequence, board_size
        )
        if blocked is not None:
            await ctx.followup.send(self._ROLL_REFUSALS[blocked], ephemeral=True)
            return

        modifier = await asyncio.to_thread(
            database.get_pending_modifier, team['id']
        )

        team_role = ctx.guild.get_role(team['role_id'])
        if team_role is None:
            await ctx.followup.send(
                "Your team's Discord role is missing; a mod needs to fix the team setup.",
                ephemeral=True,
            )
            return

        has_image = await candyland_ceremony.thread_has_proof_image(
            self.bot, thread_row['thread_id'], team['role_id']
        )
        if not has_image:
            await ctx.followup.send(
                f'No proof image in <#{thread_row["thread_id"]}> yet.', ephemeral=True
            )
            return

        die, to_sequence = candyland_roll.roll_move(
            from_sequence, board_size, modifier
        )

        movement_id = await asyncio.to_thread(
            database.advance_team_by_roll,
            team['id'], die, from_sequence, to_sequence,
            thread_row['thread_id'], ctx.author.id, state['last_movement_id'],
        )
        if movement_id is None:
            await ctx.followup.send(
                'Another roll for your team just landed first - check the board and try again.',
                ephemeral=True,
            )
            return

        # --- commit point passed: the roll counts from here no matter what ---

        art = dice_art.render(die)
        final = to_sequence == board_size
        final_tag = '  🏁 **FINAL TILE!**' if final else ''
        mod_tag = f'  _({candyland_bounty.BOUNTY_NAMES[modifier].lower()})_' if modifier else ''
        announcement = await ctx.channel.send(
            f'🎲 {ctx.author.mention} rolled for **{team["name"]}**!\n'
            f'**{die}**  ·  tile {from_sequence} → **{to_sequence}**{final_tag}{mod_tag}\n'
            f'{art}',
            allowed_mentions=discord.AllowedMentions(users=False, roles=False),
        )
        await ctx.followup.send('Your roll is in - see the board above.', ephemeral=True)

        result = await candyland_ceremony.run_post_roll_ceremony(
            self.bot, database, team, team_role, self.mainbingo_channel_id,
            to_sequence, thread_row,
        )

        if result['new_thread_id'] and not final:
            try:
                await announcement.edit(
                    content=announcement.content
                    + f'\n➡️ Next tile: <#{result["new_thread_id"]}>',
                    allowed_mentions=discord.AllowedMentions(users=False, roles=False),
                )
            except discord.HTTPException:
                pass
        await asyncio.to_thread(
            database.write_audit, ctx.author.id, 'roll',
            {'event_slug': event['slug'], 'team_id': team['id'], 'die': die,
             'from': from_sequence, 'to': to_sequence, 'movement_id': movement_id,
             'modifier': modifier,
             'ceremony': result['steps'], 'ceremony_failures': result['failures']},
        )

        if result['failures']:
            await candyland_ceremony.alert_mods(
                self.bot, self.moderator_channel_id, team, die, from_sequence,
                to_sequence, result,
            )

    @candyland.command(name='bounty',
                       description="Take a bounty against your team's current tile")
    async def bounty(self, ctx,
                     bounty_key: discord.Option(
                         str, 'Which bounty to take',
                         choices=candyland_bounty.BOUNTY_KEYS)):
        if ctx.channel.id != self.mainbingo_channel_id:
            await ctx.respond(
                f'`/candyland bounty` only works in <#{self.mainbingo_channel_id}>.',
                ephemeral=True,
            )
            return

        await ctx.defer(ephemeral=True)

        event = await asyncio.to_thread(database.get_active_event)
        if event is None:
            await ctx.followup.send(
                'No live event - ask a mod to run `/candyland start`.',
                ephemeral=True,
            )
            return

        teams = await asyncio.to_thread(database.get_teams, event['id'])
        caller_role_ids = {r.id for r in ctx.author.roles}
        team, refusal = candyland_roll.resolve_caller_team(teams, caller_role_ids)
        if refusal is not None:
            await ctx.followup.send(self._BOUNTY_REFUSALS[refusal], ephemeral=True)
            return

        thread_row = await asyncio.to_thread(database.get_open_thread, team['id'])
        if thread_row is None:
            await ctx.followup.send(
                'No active tile - has the event started?', ephemeral=True,
            )
            return

        state = await asyncio.to_thread(database.get_team_state, team['id'])
        from_sequence = state['current_sequence']

        if thread_row['tile_sequence'] != from_sequence:
            await ctx.followup.send(
                self._BOUNTY_REFUSALS[candyland_roll.OUT_OF_SYNC], ephemeral=True,
            )
            return

        if candyland_board.is_board_edge_tile(from_sequence):
            await ctx.followup.send(
                "Bounties can't be taken on the first or last tile of a board.",
                ephemeral=True,
            )
            return

        last_bounty = await asyncio.to_thread(
            database.get_last_bounty_since_roll, team['id']
        )
        if last_bounty is not None:
            last_name = candyland_bounty.BOUNTY_NAMES[last_bounty]
            if last_bounty not in candyland_bounty.SOFT_LOCK_KEYS:
                await ctx.followup.send(
                    f"Your team's last bounty was **{last_name}**. Complete "
                    'this tile and roll before taking another bounty.',
                    ephemeral=True,
                )
                return
            if bounty_key not in candyland_bounty.MOVE_KEYS:
                await ctx.followup.send(
                    f'Your team already took the **{last_name}** bounty since '
                    'its last roll. Only Retreat or Advance can follow it, '
                    'otherwise complete this tile and roll.',
                    ephemeral=True,
                )
                return

        team_role = ctx.guild.get_role(team['role_id'])
        if team_role is None:
            await ctx.followup.send(
                "Your team's Discord role is missing; a mod needs to fix the "
                'team setup.', ephemeral=True,
            )
            return

        result = await asyncio.to_thread(
            database.claim_bounty, team['id'], bounty_key, ctx.author.id,
            state['last_movement_id'],
        )
        if not result['ok']:
            if result['reason'] == 'already_used':
                name = candyland_bounty.BOUNTY_NAMES[bounty_key]
                await ctx.followup.send(
                    f'Your team has already used the **{name}** bounty on this '
                    'board.', ephemeral=True,
                )
            else:  # 'conflict'
                await ctx.followup.send(
                    'The board just changed - check it and try again.',
                    ephemeral=True,
                )
            return

        # --- commit point passed: the bounty counts from here ---

        name = candyland_bounty.BOUNTY_NAMES[bounty_key]
        move_line = ''
        if result['moved']:
            move_line = (f'\ntile {result["from_sequence"]} -> '
                         f'**{result["to_sequence"]}**')
        await ctx.channel.send(
            f'🎁 {ctx.author.mention} took the **{name}** bounty for '
            f'**{team["name"]}**!{move_line}\n'
            f'{candyland_bounty.BOUNTY_MECHANIC[bounty_key]}',
            allowed_mentions=discord.AllowedMentions(users=False, roles=False),
        )
        await ctx.followup.send('Your bounty is in - see the board above.',
                                ephemeral=True)

        # Every bounty archives the team's current thread and opens a fresh,
        # labelled one so the next roll's proof scan starts clean. That thread's
        # starter message already announces the bounty, so only fall back to a
        # plain note if it failed to open.
        cer = await candyland_ceremony.run_bounty_thread_ceremony(
            self.bot, database, team, team_role, self.mainbingo_channel_id,
            bounty_key, result['to_sequence'], thread_row,
        )

        if cer is None or not cer['open_thread_id']:
            await candyland_ceremony.post_bounty_note(
                self.bot, thread_row['thread_id'], bounty_key
            )

        await asyncio.to_thread(
            database.write_audit, ctx.author.id, 'bounty',
            {'event_slug': event['slug'], 'team_id': team['id'],
             'bounty_key': bounty_key, 'from': result['from_sequence'],
             'to': result['to_sequence'], 'moved': result['moved'],
             'movement_id': result['movement_id'],
             'ceremony': cer['steps'] if cer else None,
             'ceremony_failures': cer['failures'] if cer else None},
        )

        if cer and cer['failures']:
            await candyland_ceremony.alert_mods(
                self.bot, self.moderator_channel_id, team, 0,
                result['from_sequence'], result['to_sequence'], cer,
            )

    @candyland.command(name='bounties',
                       description="List your team's bounty pool")
    async def bounties(self, ctx):
        await ctx.defer(ephemeral=True)

        event = await asyncio.to_thread(database.get_active_event)
        if event is None:
            await ctx.followup.send(
                'No live event - ask a mod to run `/candyland start`.',
                ephemeral=True,
            )
            return

        teams = await asyncio.to_thread(database.get_teams, event['id'])
        caller_role_ids = {r.id for r in ctx.author.roles}
        team, refusal = candyland_roll.resolve_caller_team(teams, caller_role_ids)
        if refusal is not None:
            await ctx.followup.send(self._BOUNTY_REFUSALS[refusal], ephemeral=True)
            return

        state = await asyncio.to_thread(database.get_team_state, team['id'])
        board_number = candyland_board.board_of(state['current_sequence'])
        used = await asyncio.to_thread(
            database.get_bounty_uses, team['id'], board_number
        )
        used_keys = {row['bounty_key'] for row in used}

        lines = [f'**{team["name"]}** bounty pool:']
        for key in candyland_bounty.BOUNTY_KEYS:
            name = candyland_bounty.BOUNTY_NAMES[key]
            lines.append(f'~~{name}~~' if key in used_keys else f'**{name}**')

        await ctx.followup.send('\n'.join(lines), ephemeral=True)

    @commands.check(is_moderator)
    @candyland.command(name='clear', description='TESTING ONLY: wipe an event and reset it to setup')
    async def clear(self, ctx,
                    event_slug: discord.Option(str, 'Event slug')):
        event = await asyncio.to_thread(database.get_event, event_slug)
        if event is None:
            await ctx.respond(f'No candyland event with slug **{event_slug}**.')
            return

        await ctx.defer()

        teams = await asyncio.to_thread(database.get_teams, event['id'])
        thread_rows = await asyncio.to_thread(database.get_all_tile_threads, event['id'])

        threads = await candyland_ceremony.delete_tile_threads(
            self.bot, [r['thread_id'] for r in thread_rows]
        )
        forums = await candyland_ceremony.delete_team_forums(
            self.bot, [t['forum_channel_id'] for t in teams]
        )
        roles = await candyland_ceremony.delete_team_roles(
            ctx.guild, [t['role_id'] for t in teams],
            {self.moderator_role_id, self.event_planner_role_id},
        )

        await asyncio.to_thread(database.clear_event_teams, event['id'])
        await asyncio.to_thread(
            database.write_audit, ctx.author.id, 'clear',
            {'event_slug': event_slug, 'event_id': event['id'],
             'threads_deleted': len(threads['deleted']),
             'threads_missing': len(threads['missing']),
             'threads_failed': threads['failed'],
             'forums_deleted': len(forums['deleted']),
             'forums_missing': len(forums['missing']),
             'forums_failed': forums['failed'],
             'roles_deleted': len(roles['deleted']),
             'roles_missing': len(roles['missing']),
             'roles_failed': roles['failed']},
        )

        lines = [
            f'Cleared **{event_slug}**: team rows dropped (movement, tile-thread '
            f'records, team state and bounty use cascade), status back to `setup`.',
            f'Discord: {len(threads["deleted"])} tile thread(s), '
            f'{len(forums["deleted"])} forum(s), {len(roles["deleted"])} role(s) deleted; '
            f'{len(threads["missing"])}/{len(forums["missing"])}/{len(roles["missing"])} '
            f'thread/forum/role already gone.',
            'The `Fall 2026 Bingo` category and the Moderator / Event Planner / chikbot '
            'roles are untouched.',
        ]
        failed = threads['failed'] + forums['failed'] + roles['failed']
        if failed:
            lines.append('Could not delete: ' + '; '.join(failed))
        lines.append('Re-run `/candyland team-add` for each team to set up again.')
        await ctx.respond('\n'.join(lines))

    async def cog_command_error(self, ctx, error):
        if isinstance(error, discord.errors.CheckFailure):
            await ctx.respond('Mods only.', ephemeral=True)
        else:
            raise error


def setup(bot):
    bot.add_cog(Candyland(bot))
