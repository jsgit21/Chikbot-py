import discord
import os
import sys
import time
import asyncio
import pymysql
import random

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TOKEN')
DEV_CHANNEL_ID = int(os.getenv('PERSONAL_DEV_CHANNEL'))

db = pymysql.connect(
    database='Discord',
    read_default_file='~/.my.cnf',
    autocommit=True,
)

intents = discord.Intents.default()
intents.message_content = True

chikbot = discord.Bot()
chikbot.db = db

# Cogs
chikbot.load_extension('cogs.user_goals.user_goals')

def get_random_emoji():
    emoji_list = chikbot.emojis
    max_rand = len(emoji_list)-1
    pick = random.randint(0, max_rand)
    emoji = emoji_list[pick]
    return f'<{emoji.name}:{emoji.id}>'

async def register_author(author):
    # Blocking operation offloaded to a separate thread
    await asyncio.to_thread(register_author_thread, author)

def register_author_thread(author):
    cursor = db.cursor()

    query = """
        insert ignore into Discord.user (user_id, username)
        values (%s, %s)
    """
    values = (
        author.id,
        author.name,
    )
    cursor.execute(query, values)

    display_name = author.nick if author.nick else author.global_name

    query = """
        insert ignore into Discord.user_alias (user_id, alias)
        values (%s, %s)
    """
    values = (
        author.id,
        display_name,
    )
    cursor.execute(query, values)

async def random_emoji_reaction(message, max):
    send_value = random.randint(0,max)
    if send_value > max-2:
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

    if message.author.bot:
        return

    if message.webhook_id:
        return

    await register_author(message.author)
    await random_emoji_reaction(message, 50)


chikbot.run(TOKEN)
