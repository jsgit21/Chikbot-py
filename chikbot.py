import discord
import os
import asyncio
import random

from dotenv import load_dotenv
import database.db_methods as database

load_dotenv()
TOKEN = os.getenv('TOKEN')
DEV_CHANNEL_ID = int(os.getenv('PERSONAL_DEV_CHANNEL'))
GM_CHANNEL_ID = int(os.getenv('GM_CHANNEL'))
CHIKBOT_ID = int(os.getenv('CHIKBOT_ID'))
GM_EMOJI = discord.PartialEmoji(name='gm', id=874033154313314414)

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

chikbot = discord.Bot(intents=intents)


# Cogs
chikbot.load_extension('cogs.user_goals.user_goals')
chikbot.load_extension('cogs.wise_old_man.wise_old_man')
chikbot.load_extension('cogs.runescape_logger.runescape_logger')


def get_random_emoji():
    emoji_list = chikbot.emojis
    max_rand = len(emoji_list) - 1
    pick = random.randint(0, max_rand)
    emoji = emoji_list[pick]
    return f'<{emoji.name}:{emoji.id}>'


def get_random_emoji_v2() -> discord.Emoji:
    return random.choice(chikbot.emojis)


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


@chikbot.event
async def on_ready():
    online_message = f'We have logged in as {chikbot.user}'
    channel = chikbot.get_channel(DEV_CHANNEL_ID)

    print(online_message)
    await channel.send(online_message)


@chikbot.event
async def on_message(message):
    if message.author.bot:
        return

    await asyncio.to_thread(database.register_user, message.author)
    await random_emoji_reaction(message, 50)
    await gm_reply(message)


chikbot.run(TOKEN)
