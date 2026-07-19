import os
import random
import datetime
import discord
from discord.ext import tasks, commands

from .rolecheck import get_misranked_users, bulk_update_outdated_users, get_user_roles, get_members_with_ranks
from . import wom_utilities as utils
from .identity import db as identity_db
from .shared import checks
import database.db_methods as database
from shared import tz

class Wise_Old_Man(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.MOD_CHANNEL_ID = checks.moderator_channel_id()
        self.DEV_CHANNEL_ID = int(os.getenv('PERSONAL_DEV_CHANNEL'))
        self.rolecheck.start()
        self.update_wom_group.start()


    # Commands
    @commands.check(checks.is_moderator)
    @discord.slash_command(description='''Sync the whitelist that controls access to Dink Webhooks.''')
    async def sync_wom_whitelist(self, ctx):
        all_members = get_members_with_ranks()
        changes = database.update_local_wom_group(all_members)

        if changes['total_changes'] == 0:
            response = (
                'There were no updates found for the WOM group.\n'
                'Ensure the clan was Sync\'d to WOM through the game.\n'
                '-# Ask Joe or Nick to update if needed'
            )
            await ctx.respond(response)
        else:
            msg = utils.format_wom_whitelist_changes(changes)
            await ctx.respond(msg)

    @sync_wom_whitelist.error
    async def sync_wom_whitelist_error(self, ctx, error):
        if isinstance(error, discord.errors.CheckFailure):
            luigi_fu = discord.utils.get(self.bot.emojis, name='luigi_fu')
            sit = discord.utils.get(self.bot.emojis, name='Sit')
            msg = f'Moderator privileges are required for this command {sit} {luigi_fu}'
            await ctx.respond(msg)
        else:
            raise Exception(error)


    @property
    def mod_channel(self):
        return self.bot.get_channel(self.MOD_CHANNEL_ID)


    @property
    def dev_channel(self):
        return self.bot.get_channel(self.DEV_CHANNEL_ID)


    def format_output(self, users):
        # Returns a list of messages to be sent
        final_output = []
        message_buffer = ['__Ranks need updates__:']
        for user in users:
            username = user['username']
            curr_role = user['current_rank']
            curr_emoji = user['current_rank_emoji']
            new_role = user['determined_rank']
            new_emoji = user['determined_rank_emoji']
            total =  user.get('total')

            emoji_list = self.bot.emojis
            curr_emoji = discord.utils.get(emoji_list, name=curr_emoji)
            new_emoji = discord.utils.get(emoji_list, name=new_emoji)

            msg = f'{curr_emoji} `{curr_role:<11}` -> {new_emoji} `{new_role:<11}`  [`{total:>4}`]  **{username}**'

            # Check the length of current message
            # Determined if we will reach the 2000 character limit when adding
            # the next message
            curr_length = len('\n'.join(message_buffer))
            added_newlines = len(message_buffer) - 1
            new_length = curr_length + len(msg) + added_newlines

            if new_length > 1800:
                final_output.append('\n'.join(message_buffer))
                # Clear out message buffer to start a new message
                message_buffer = []

            message_buffer.append(msg)

        # Catch any messages left in the buffer
        if len(message_buffer) > 0:
            final_output.append('\n'.join(message_buffer))

        return final_output


    def get_guests(self):
        guests = get_user_roles(rank='member')

        guest_names = [guest['username'] for user_id, guest in guests.items()]
        return ', '.join(guest_names)

    def sync_wom_group_to_db(self):
        all_members = get_members_with_ranks()
        changes = database.update_local_wom_group(all_members)

        if changes['total_changes'] > 0:
            msg = utils.format_wom_whitelist_changes(changes)
            return msg
        return None

    def get_unlinked_backfill_nudge(self):
        # Occasional, capped nudge so backfill chips away without spamming the mod channel daily
        if random.randint(1, 3) != 1:
            return None

        unlinked = identity_db.get_unlinked_members()
        if not unlinked:
            return None

        sample = random.sample(unlinked, min(3, len(unlinked)))
        names = ', '.join(member['rsn'] for member in sample)
        return f'-# Still unlinked: {names}. Use `/wom link` to connect them to a Discord member.'

    # tzinfo must stay explicit: discord.py's tasks.loop forces UTC on a naive
    # time= regardless of the host OS's timezone, so a naive hour=9 here would
    # actually fire at 9:00 UTC, not 9:00 AM ET.
    @tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=tz.ET))
    async def update_wom_group(self):
        sync_message = self.sync_wom_group_to_db()
        if sync_message:
            await self.mod_channel.send(sync_message)

        message = bulk_update_outdated_users()
        await self.dev_channel.send(message)

        nudge = self.get_unlinked_backfill_nudge()
        if nudge:
            await self.mod_channel.send(nudge)


    @update_wom_group.before_loop
    async def before_update_wom_group(self):
        await self.bot.wait_until_ready()


    # tzinfo must stay explicit: discord.py's tasks.loop forces UTC on a naive
    # time= regardless of the host OS's timezone, so a naive hour=10 here would
    # actually fire at 10:00 UTC, not 10:00 AM ET.
    @tasks.loop(time=datetime.time(hour=10, minute=0, tzinfo=tz.ET))
    async def rolecheck(self):
        try:
            update_users = get_misranked_users()

            if len(update_users) > 0:
                output_message_list = self.format_output(update_users)

                for output_message in output_message_list:
                    await self.mod_channel.send(output_message)

                note = '-# The WOM group has to be re-syncd once ranks are changed. (Ask Joe or Nick)'
                await self.mod_channel.send(note)

                # Provide a list of guests in the group
                guest_list = self.get_guests()
                await self.mod_channel.send(f'-# Guests for WOM sync: {guest_list}')
        except Exception as e:
            print(e)
            await self.mod_channel.send('Failed to run rolecheck')
            await self.mod_channel.send(f'{str(e)}')


    @rolecheck.before_loop
    async def before_rolecheck(self):
        await self.bot.wait_until_ready()



def setup(bot):
    bot.add_cog(Wise_Old_Man(bot))

