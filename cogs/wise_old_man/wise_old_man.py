import os
import datetime
import discord
from discord.ext import tasks, commands

from .rolecheck import get_misranked_users, bulk_update_outdated_users, get_user_roles
import database.db_methods as database

class Wise_Old_Man(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.MOD_CHANNEL_ID = int(os.getenv('MODERATOR_CHANNEL'))
        self.DEV_CHANNEL_ID = int(os.getenv('PERSONAL_DEV_CHANNEL'))
        self.rolecheck.start()
        self.update_wom_group.start()

        print('Syncing local wom group!')
        self.sync_wom_group_to_db()


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

            if new_length > 2000:
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
        all_members = get_user_roles()
        all_members = [
            [user_id, member['username'], member['current_rank']]
            for user_id, member in all_members.items()
        ]
        database.update_local_wom_group(all_members)


    @tasks.loop(time=datetime.time(hour=13, minute=00))
    async def update_wom_group(self):
        self.sync_wom_group_to_db()
        message = bulk_update_outdated_users()
        await self.dev_channel.send(message)


    @update_wom_group.before_loop
    async def before_update_wom_group(self):
        await self.bot.wait_until_ready()


    @tasks.loop(time=datetime.time(hour=14, minute=00))
    async def rolecheck(self):
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


    @rolecheck.before_loop
    async def before_rolecheck(self):
        await self.bot.wait_until_ready()



def setup(bot):
    bot.add_cog(Wise_Old_Man(bot))

