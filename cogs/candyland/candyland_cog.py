"""Casual GMers Land (candyland) admin cog - Phase A.

Phase A (this cog): the schema in database/SCHEMA.sql, the DB-access module
candyland_db.py, and the mod-gated admin commands below to create an event,
register teams, and read board state back.

Phase B (not here): /candyland roll, 1d4+1 movement, the per-tile forum-thread
ceremony, the movement writes and the state fold wired into play.
Phase C (not here): bounty logic. Phase D (not here): the website board.
"""

import asyncio

import discord
from discord.ext import commands

from . import candyland_db as database


async def is_moderator(ctx):
    mod_role = discord.utils.get(ctx.author.roles, name='Moderator', id=360455451852406797)
    return mod_role is not None


class Candyland(commands.Cog):

    candyland = discord.SlashCommandGroup('candyland', 'Casual GMers Land event admin')

    def __init__(self, bot):
        self.bot = bot

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
                       forum: discord.Option(discord.TextChannel, "Forum channel for this team's tile threads"),
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

    async def cog_command_error(self, ctx, error):
        if isinstance(error, discord.errors.CheckFailure):
            await ctx.respond('Mods only.', ephemeral=True)
        else:
            raise error


def setup(bot):
    bot.add_cog(Candyland(bot))
