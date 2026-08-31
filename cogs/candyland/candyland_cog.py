"""Casual GMers Land (candyland) admin cog - Phase A.

Phase A (this cog): the schema in database/SCHEMA.sql, the DB-access module
candyland_db_methods.py, and the mod-gated admin commands below to create an
event, register teams, and read board state back.

Phase B (not here): /candyland roll, 1d4+1 movement, the per-tile forum-thread
ceremony, the movement writes and the state fold wired into play.
Phase C (not here): bounty logic. Phase D (not here): the website board.
"""

import asyncio
import os
import random

import discord
from discord.ext import commands

from . import candyland_board
from . import candyland_ceremony
from . import candyland_db_methods as database
from cogs.roll_dice import dice_art


async def is_moderator(ctx):
    mod_role = discord.utils.get(ctx.author.roles, name='Moderator', id=360455451852406797)
    return mod_role is not None


class Candyland(commands.Cog):

    candyland = discord.SlashCommandGroup('candyland', 'Casual GMers Land event admin')

    def __init__(self, bot):
        self.bot = bot
        self.mainbingo_channel_id = int(os.getenv('MAINBINGO_CHANNEL'))
        self.moderator_channel_id = int(os.getenv('MODERATOR_CHANNEL'))

    @commands.check(is_moderator)
    @candyland.command(name='setup-event', description='Create a candyland event')
    async def setup_event(self, ctx,
                          slug: discord.Option(str, 'Unique event slug'),
                          board_slug: discord.Option(str, 'Starting board', choices=['standard', 'hard']),
                          starts_at: discord.Option(str, 'Start time, ISO-8601 UTC', required=False, default=None),
                          ends_at: discord.Option(str, 'End time, ISO-8601 UTC', required=False, default=None)):
        event_id = await asyncio.to_thread(
            database.create_event, slug, board_slug, starts_at, ends_at
        )
        await asyncio.to_thread(
            database.write_audit, ctx.author.id, 'setup-event',
            {'slug': slug, 'board_slug': board_slug, 'event_id': event_id}
        )
        await ctx.respond(f'Created candyland event **{slug}** (id `{event_id}`).')

    @commands.check(is_moderator)
    @candyland.command(name='team-add', description='Register a team for a candyland event')
    async def team_add(self, ctx,
                       event_slug: discord.Option(str, 'Event slug'),
                       name: discord.Option(str, 'Team name'),
                       role: discord.Option(discord.Role, 'Role that authorises this team to roll'),
                       forum: discord.Option(discord.ForumChannel, "Forum channel for this team's tile threads"),
                       sort_order: discord.Option(int, 'Display order', default=0)):
        event = await asyncio.to_thread(database.get_event, event_slug)
        if event is None:
            await ctx.respond(f'No candyland event with slug **{event_slug}**.')
            return

        team_id = await asyncio.to_thread(
            database.register_team, event['id'], name, role.id, forum.id, sort_order
        )
        await asyncio.to_thread(
            database.write_audit, ctx.author.id, 'team-add',
            {'event_slug': event_slug, 'name': name, 'role_id': role.id,
             'forum_channel_id': forum.id, 'team_id': team_id}
        )
        await ctx.respond(f'Registered team **{name}** (id `{team_id}`) for **{event_slug}**.')

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
                f'- **{row["name"]}**: {row["board_slug"]} tile {row["current_sequence"]} '
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
            existing = await asyncio.to_thread(database.get_open_thread, team['id'])
            if existing is not None:
                skipped.append(team['name'])
                continue
            team_role = ctx.guild.get_role(team['role_id'])
            try:
                thread = await candyland_ceremony.open_tile_thread(
                    self.bot, team['forum_channel_id'], self.mainbingo_channel_id,
                    team_role, 1,
                )
                await asyncio.to_thread(
                    database.open_tile_thread, team['id'], event['board_slug'], 1, thread.id
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
            lines.append('Skipped (already had a thread): ' + ', '.join(skipped))
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

        event = await asyncio.to_thread(database.get_active_event)
        if event is None:
            await ctx.respond(
                'No live event - ask a mod to run `/candyland start`.', ephemeral=True
            )
            return

        teams = await asyncio.to_thread(database.get_teams, event['id'])
        caller_role_ids = {r.id for r in ctx.author.roles}
        matched = [t for t in teams if t['role_id'] in caller_role_ids]
        if not matched:
            await ctx.respond('You are not on a team for this event.', ephemeral=True)
            return
        if len(matched) > 1:
            await ctx.respond('You hold more than one team role.', ephemeral=True)
            return
        team = matched[0]

        thread_row = await asyncio.to_thread(database.get_open_thread, team['id'])
        if thread_row is None:
            await ctx.respond(
                'No active tile - has the event started? Ask a mod to run `/candyland start`.',
                ephemeral=True,
            )
            return

        state = await asyncio.to_thread(database.get_team_state, team['id'])
        from_sequence = state['current_sequence']
        board_slug = state['board_slug']
        board_size = candyland_board.BOARD_SIZES[board_slug]

        if thread_row['tile_sequence'] != from_sequence:
            await ctx.respond(
                "Your team's tile thread is out of sync with the board; a mod needs to repair it.",
                ephemeral=True,
            )
            return

        if from_sequence >= board_size:
            await ctx.respond(
                'Your team is on the final tile; the board transition is handled separately.',
                ephemeral=True,
            )
            return

        has_image = await candyland_ceremony.thread_has_proof_image(
            self.bot, thread_row['thread_id'], team['role_id']
        )
        if not has_image:
            await ctx.respond(
                f'No proof image in <#{thread_row["thread_id"]}> yet.', ephemeral=True
            )
            return

        die = random.randint(1, 4) + 1
        to_sequence = min(from_sequence + die, board_size)

        movement_id = await asyncio.to_thread(
            database.advance_team_by_roll,
            team['id'], board_slug, str(die), from_sequence, to_sequence,
            thread_row['thread_id'], ctx.author.id, state['last_movement_id'],
        )
        if movement_id is None:
            await ctx.respond(
                'Another roll for your team just landed first - check the board and try again.',
                ephemeral=True,
            )
            return

        # --- commit point passed: the roll counts from here no matter what ---

        art = dice_art.render(die)
        final = ' (final tile!)' if to_sequence == board_size else ''
        await ctx.respond(
            f'🎲 **{team["name"]}** rolled **{die}** - tile {from_sequence} -> **{to_sequence}**{final}\n'
            f'```\n{art}\n```'
        )

        team_role = ctx.guild.get_role(team['role_id'])
        result = await candyland_ceremony.run_post_roll_ceremony(
            self.bot, database, team, team_role, self.mainbingo_channel_id,
            board_slug, to_sequence, thread_row,
        )
        await asyncio.to_thread(
            database.write_audit, ctx.author.id, 'roll',
            {'event_slug': event['slug'], 'team_id': team['id'], 'die': die,
             'from': from_sequence, 'to': to_sequence, 'movement_id': movement_id,
             'ceremony': result['steps'], 'ceremony_failures': result['failures']},
        )

        if result['failures']:
            await candyland_ceremony.alert_mods(
                self.bot, self.moderator_channel_id, team, die, from_sequence,
                to_sequence, result,
            )

    async def cog_command_error(self, ctx, error):
        if isinstance(error, discord.errors.CheckFailure):
            await ctx.respond('Mods only.', ephemeral=True)
        else:
            raise error


def setup(bot):
    bot.add_cog(Candyland(bot))
