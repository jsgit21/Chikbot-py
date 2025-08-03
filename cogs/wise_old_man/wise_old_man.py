import os
import datetime
import discord
from discord.ext import tasks, commands

from .rolecheck import get_misranked_users, bulk_update_outdated_users

class Wise_Old_Man(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.MOD_CHANNEL_ID = int(os.getenv('MODERATOR_CHANNEL'))
        self.DEV_CHANNEL_ID = int(os.getenv('PERSONAL_DEV_CHANNEL'))
        self.rolecheck.start()
        self.update_wom_group.start()


    @property
    def mod_channel(self):
        return self.bot.get_channel(self.MOD_CHANNEL_ID)


    @property
    def dev_channel(self):
        return self.bot.get_channel(self.DEV_CHANNEL_ID)


    def format_users(self, users):
        output_list = ['__Ranks need updates__:']
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

            output_list.append(f'{curr_emoji} `{curr_role:<11}` -> {new_emoji} `{new_role:<11}`  [`{total:>4}`]  **{username}**')

        return '\n'.join(output_list)


    @tasks.loop(time=datetime.time(hour=13, minute=00))
    async def update_wom_group(self):
        message = bulk_update_outdated_users()
        await self.dev_channel.send(message)


    @update_wom_group.before_loop
    async def before_update_wom_group(self):
        await self.bot.wait_until_ready()


    @tasks.loop(time=datetime.time(hour=14, minute=00))
    async def rolecheck(self):
        update_users = get_misranked_users()

        # TODO
        # This needs to be changed to paginate, in the case of many users
        # it can easily hit the message limit
        # Also need to fix the server time, it is 4 hours ahead

        if len(update_users) > 0:
            output_message = self.format_users(update_users)

            await self.mod_channel.send(output_message)
            note = '-# The WOM group has to be re-syncd once ranks are changed. (Ask Joe or Nick)'
            await mod_channel.send(note)


    @rolecheck.before_loop
    async def before_rolecheck(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Wise_Old_Man(bot))

