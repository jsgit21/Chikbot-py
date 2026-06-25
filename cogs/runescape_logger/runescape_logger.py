import os
import discord
from discord.ext import commands
import database.db_methods as database


class Runescape_Logger(commands.Cog):

    dink_channels = ['ACHIEVEMENTS', 'BOSSING', 'DED', 'LEVELS', 'PETS', 'LOOT']

    def __init__(self, bot):
        self.bot = bot
        self.WEBHOOK_GRAVEYARD = int(os.getenv('WEBHOOK_GRAVEYARD'))
        self.CHIKEN_TENDERS_GUILD = int(os.getenv('CHIKEN_TENDERS_GUILD'))
        self.dink_webhooks = {int(os.getenv(f'{c}_WEBHOOK')): c for c in self.dink_channels}
        self.dink_channel_ids = {c: int(os.getenv(f'{c}_CHANNEL')) for c in self.dink_channels}

    @commands.Cog.listener()
    async def on_ready(self):
        await self.update_dink_channels()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.webhook_id in self.dink_webhooks:
            await self.process_dink_message(message)

    async def get_webhook_for_channel(self, channel):
        webhook_id = int(os.getenv(f'{channel}_WEBHOOK_FWD'))
        guild_webhooks = await self.bot.get_guild(self.CHIKEN_TENDERS_GUILD).webhooks()
        webhook = next((h for h in guild_webhooks if h.id == webhook_id), None)
        return webhook

    async def process_dink_message(self, message):
        webhook_graveyard = self.bot.get_channel(self.WEBHOOK_GRAVEYARD)
        if not message.embeds:
            output = (
                f'Discord User: `{message.author}`\n'
                f'Global Name: `{message.author.global_name}`\n\n'
                f'{message.content}\n\n'
                f'-# {message}'
            )
            await webhook_graveyard.send(content=output)
            await message.delete()
            return

        embed = message.embeds[0]
        original_message_id = message.id
        channel_name = self.dink_webhooks[message.webhook_id]

        if embed.timestamp == None:
            embed.timestamp = message.created_at
        dink_icon = 'https://github.com/pajlads/DinkPlugin/raw/master/icon.png'
        embed.set_footer(text=f'Powered by Dink | Casual GMers', icon_url=dink_icon)

        embed.colour = 0xFFDE21
        seasonal = '[Seasonal]' in embed.title
        if seasonal:
            embed.colour = 0xCC0D06

        rsn = embed.author.name
        group_member = database.check_local_wom(rsn)

        if group_member and not seasonal:
            webhook = await self.get_webhook_for_channel(channel_name)
            await webhook.send(embed=embed, username=webhook.name.replace('fwd ', ''))
        else:
            await webhook_graveyard.send(embed=embed)

        database.register_latest_dink_transaction(channel_name, original_message_id)

    async def update_dink_channels(self):
        for channel in self.dink_channels:
            message_id = database.get_latest_dink_transaction(channel)
            dink_channel = self.bot.get_channel(self.dink_channel_ids[channel])
            message_target = discord.Object(id=message_id)

            while True:
                unfwded_messages = await dink_channel.history(after=message_target).flatten()

                if len(unfwded_messages) == 0:
                    break

                for message in unfwded_messages:
                    await self.process_dink_message(message)

                message_target = unfwded_messages[-1]


def setup(bot):
    bot.add_cog(Runescape_Logger(bot))
