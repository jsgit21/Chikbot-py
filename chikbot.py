import discord
import os
import io
import sys
import time
import asyncio
import aiohttp
import pymysql
import random

from dotenv import load_dotenv
import database.db_methods as database

load_dotenv()
TOKEN = os.getenv('TOKEN')
DEV_CHANNEL_ID = int(os.getenv('PERSONAL_DEV_CHANNEL'))
GM_CHANNEL_ID = int(os.getenv('GM_CHANNEL'))
WEBHOOK_GRAVEYARD = int(os.getenv('WEBHOOK_GRAVEYARD'))
CHIKBOT_ID = int(os.getenv('CHIKBOT_ID'))
CHIKEN_TENDERS_GUILD = int(os.getenv('CHIKEN_TENDERS_GUILD'))
GM_EMOJI = discord.PartialEmoji(name='gm', id=874033154313314414)

dink_channels = ['ACHIEVEMENTS', 'BOSSING', 'DED', 'LEVELS', 'PETS', 'LOOT']
dink_webhooks = {int(os.getenv(f'{c}_WEBHOOK')):c for c in dink_channels}
dink_channel_ids = {c:int(os.getenv(f'{c}_CHANNEL')) for c in dink_channels}

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

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


def get_random_emoji_v2() -> discord.Emoji:
    return random.choice(chikbot.emojis)


async def get_webhook_for_channel(channel, guild=CHIKEN_TENDERS_GUILD):
    webhook_id = int(os.getenv(f'{channel}_WEBHOOK_FWD'))
    guild_webhooks = await chikbot.get_guild(CHIKEN_TENDERS_GUILD).webhooks()
    webhook = next((h for h in guild_webhooks if h.id == webhook_id), None)
    return webhook


async def random_emoji_reaction(message, max):
    send_value = random.randint(0, max)
    if send_value > max - 2:
        reaction = get_random_emoji()
        await message.add_reaction(reaction)


async def gm_reply(message):
    if message.channel.id != GM_CHANNEL_ID:
        return
    if random.randint(1, 20) == 1:
        random_emoji = get_random_emoji_v2()
        await message.reply(f"{GM_EMOJI} {random_emoji}")


async def get_image_bytes(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                image_bytes = await response.read()
                return image_bytes


async def process_dink_message(message):
    webhook_graveyard = chikbot.get_channel(WEBHOOK_GRAVEYARD)
    # Dink messages should contain embeds
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
    channel_name = dink_webhooks[message.webhook_id]

    # Edit embed data for consistency
    if embed.timestamp == None:
        embed.timestamp = message.created_at
    dink_icon = 'https://github.com/pajlads/DinkPlugin/raw/master/icon.png'
    embed.set_footer(text=f'Powered by Dink | Casual GMers', icon_url=dink_icon)

    embed.colour = 0xFFDE21
    seasonal = '[Seasonal]' in embed.title
    if seasonal:
        embed.colour = 0xCC0D06

    # Ensure the rsn coming through dink is part of our group
    rsn = embed.author.name
    group_member = database.check_local_wom(rsn)

    if group_member and not seasonal:
        # Forward the embed to the user facing channels via webhook fwds
        webhook = await get_webhook_for_channel(channel_name)
        await webhook.send(embed=embed, username=webhook.name.replace('fwd ', ''))
    else:
        await webhook_graveyard.send(embed=embed)

    # Register the message_id of the original dink message with the database;
    # This way we know what was the last dink message that chikbot forwarded
    database.register_latest_dink_transaction(channel_name, original_message_id)


async def update_dink_channels():
    # Lets do a check to make sure Dink channels are up to date
    for channel in dink_channels:
        # Get latest transaction for channel
        message_id = database.get_latest_dink_transaction(channel)

        # Fetch all messages from that channel after that message id
        dink_channel = chikbot.get_channel(dink_channel_ids[channel])
        message_target = discord.Object(id=message_id)

        while True:
            # While using the after argument, this will return at most 100
            # messsages, so we can loop to make sure we forward everything
            unfwded_messages = await dink_channel.history(after=message_target).flatten()

            if len(unfwded_messages) == 0:
                break

            for message in unfwded_messages:
                await process_dink_message(message)

            # The new target is the last message in the list, to see if there
            # are any more messages beyond that
            message_target = unfwded_messages[-1]


@chikbot.event
async def on_ready():
    online_message = f'We have logged in as {chikbot.user}'
    channel = chikbot.get_channel(DEV_CHANNEL_ID)

    print(online_message)
    await channel.send(online_message)

    await update_dink_channels()


@chikbot.event
async def on_message(message):

    # Process messages that were sent via webhook in the Dink channels
    if message.webhook_id in dink_webhooks:
        await process_dink_message(message)
        return

    if message.author.bot:
        return

    await asyncio.to_thread(database.register_user, message.author)
    await random_emoji_reaction(message, 50)
    await gm_reply(message)


chikbot.run(TOKEN)
