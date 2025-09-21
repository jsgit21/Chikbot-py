import discord
import os
import sys
import time
import asyncio
import pymysql
import random

from dotenv import load_dotenv
import database.db_methods as database

load_dotenv()
TOKEN = os.getenv('TOKEN')
DEV_CHANNEL_ID = int(os.getenv('PERSONAL_DEV_CHANNEL'))
WEBHOOK_GRAVEYARD = int(os.getenv('WEBHOOK_GRAVEYARD'))

intents = discord.Intents.default()
intents.message_content = True

chikbot = discord.Bot(intents=intents)

# Cogs
chikbot.load_extension('cogs.user_goals.user_goals')
chikbot.load_extension('cogs.wise_old_man.wise_old_man')

def get_random_emoji():
    emoji_list = chikbot.emojis
    max_rand = len(emoji_list) - 1
    pick = random.randint(0, max_rand)
    emoji = emoji_list[pick]
    return f'<{emoji.name}:{emoji.id}>'


async def random_emoji_reaction(message, max):
    send_value = random.randint(0, max)
    if send_value > max - 2:
        reaction = get_random_emoji()
        await message.add_reaction(reaction)


@chikbot.event
async def on_ready():
    online_message = f'We have logged in as {chikbot.user}'
    channel = chikbot.get_channel(DEV_CHANNEL_ID)

    print(online_message)
    await channel.send(online_message)


@chikbot.event
async def on_message(message):

    # Process messages that were sent via webhook
    if message.webhook_id:
        channel = chikbot.get_channel(WEBHOOK_GRAVEYARD)

        # Dink messages should contain embeds
        if not message.embeds:
            output = (
                f'Discord User: `{message.author}`\n'
                f'Global Name: `{message.author.global_name}`\n\n'
                f'{message.content}\n\n'
                f'-# {message}'
            )
            await channel.send(content=output)
            await message.delete()
            return

        # Ensure the rsn coming through dink is part of our group
        rsn = message.embeds[0].author.name
        group_member = database.check_local_wom(rsn)

        if not group_member:
            await channel.send(embed=message.embeds[0])
            await message.delete()
        return

    if message.author.bot:
        return

    await asyncio.to_thread(database.register_user, message.author)
    await random_emoji_reaction(message, 50)


chikbot.run(TOKEN)
