import os
import sys
import asyncio

import discord
from discord.ext import commands

from . import goal_db_methods as database
from . import goal_utilities as utils

# Cogs are modules that can be added to the bot
# Class inherits from commands.Cog

class User_Goals(commands.Cog):

    goals = discord.SlashCommandGroup("goals", "Viewing and configuring goals")

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db


    # Commands
    @goals.command(description="How to use goal commands")
    async def help(self, ctx):
        response = (
            'You can use the slash commands `/goals` to configure personal goals\n\n'
            '- __Setting goals__:\n'
            '  - `/goals add [goal]`\n'
            '- __Setting sub goals__:\n'
            '  - `/goals add [goal] [parent_goal_number]`\n'
            '- __Viewing your goals__:\n'
            '  - `/goals view `\n'
            '  - `/goals view_detailed `\n'
            '- __Modifying your goals__:\n'
            '  - `/goals edit [goal_number] [goal]`\n'
            '  - `/goals complete [goal_number]`\n'
            '  - `/goals delete [goal_number]`\n\n'
            'You can view goals for anyone in the server:\n'
            'Right-click their profile > **Apps** > **view_goals**'
        )

        await ctx.respond(response)


    @goals.command(description="Add personal goals")
    async def add(self, ctx,
                       goal: discord.Option(str, "Your personal goal", required=True),
                       parent_goal_number: discord.Option(int, "Optional parent goal number", required=False) = None):
        user_id = ctx.author.id
        insert_id = await asyncio.to_thread(database.add_goal, self.db, user_id, goal, parent_goal_number)

        if insert_id is None:
            await ctx.respond(f'Unable to add a goal for goal_number: **{parent_goal_number}**')
            return

        await ctx.respond(f'✅ **Goal added** - {goal}')


    @goals.command(description="View goals")
    async def view(self, ctx):
        user_id = ctx.author.id
        goals = await asyncio.to_thread(database.get_goals, self.db, user_id)

        goals_view = utils.format_goals(goals)
        await ctx.respond(goals_view)


    @goals.command(description="View goals with details")
    async def view_detailed(self, ctx):
        user_id = ctx.author.id
        goals = await asyncio.to_thread(database.get_goals, self.db, user_id)

        goals_view = utils.format_goals(goals, verbose=True)
        await ctx.respond(goals_view)


    @goals.command(description="Get details for a specific goal")
    async def detail(self, ctx, goal_number: int):
        user_id = ctx.author.id
        goal = await asyncio.to_thread(database.get_goals, self.db, user_id, goal_number)

        if goal is None:
            await ctx.respond(f'Unable to get details for goal number: **{goal_number}**')
            return

        goal_details = utils.format_detailed_goal(goal)
        await ctx.respond(goal_details)


    @goals.command(description="Complete goal")
    async def complete(self, ctx, goal_number: int):
        user_id = ctx.author.id
        goal_row = await asyncio.to_thread(database.complete_goal, self.db, user_id, goal_number)

        if goal_row is None:
            await ctx.respond(f'Unable to complete goal number: **{goal_number}**')
            return

        if goal_row['completed']:
            await ctx.respond(f'🎉 **Goal completed** - {goal_row["goal"]}')
        else:
            await ctx.respond(f'**Removed goal completion** - {goal_row["goal"]}')


    @goals.command(description="Delete goal")
    async def delete(self, ctx, goal_number: int):
        user_id = ctx.author.id
        goal_row = await asyncio.to_thread(database.delete_goal, self.db, user_id, goal_number)

        if goal_row is None:
            await ctx.respond(f'Unable to delete goal number: **{goal_number}**')
            return

        response = (
            f'❌ **Goal deleted** - {goal_row["goal"]}\n'
            'Goal numbers may have shifted!'
        )
        await ctx.respond(response)



    @goals.command(description="Edit goal")
    async def edit(self, ctx, goal_number: int, goal: str):
        user_id = ctx.author.id
        old_goal_row = await asyncio.to_thread(database.edit_goal, self.db, user_id, goal_number, goal)

        if old_goal_row is None:
            await ctx.respond(f'Unable to edit goal number: **{goal_number}**')
            return

        await ctx.respond(f'📝 **Goal edited** - **{goal_number}**: {goal}')


    # User commands
    @discord.user_command()
    async def view_goals(self, ctx, member):
        user_id = member.id
        user_name = member.nick or member.global_name or member.name
        goals = await asyncio.to_thread(database.get_goals, self.db, user_id)

        if len(goals) == 0:
            await ctx.respond(f'__**{user_name}**__ has no goals set.')
            return

        response = f'__Goals for **{user_name}**__:\n'
        goals_view = utils.format_goals(goals)
        response += goals_view
        await ctx.respond(response)


    @discord.user_command()
    async def view_goals_detailed(self, ctx, member):
        user_id = member.id
        user_name = member.nick or member.global_name or member.name
        goals = await asyncio.to_thread(database.get_goals, self.db, user_id)

        if len(goals) == 0:
            await ctx.respond(f'__**{user_name}**__ has no goals set.')
            return

        response = f'__**Goals for {user_name}**__:\n'
        goals_view = utils.format_goals(goals, verbose=True)
        response += goals_view
        await ctx.respond(response)


def setup(bot):
    # Called by Pycord to setup the cog
    bot.add_cog(User_Goals(bot))
