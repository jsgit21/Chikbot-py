import random
import re

import discord
from discord.ext import commands

TRIGGER_WORDS = {
    "egg",
    "cluck",
    "bawk",
    "feathers",
    "cock",
    "chicken",
    "corp",
    "scared",
    "rooster",
    "coward",
    "poultry",
    "peck",
}
REACTION_EMOJIS = ["🐔", "🐣", "🥚", "🐓"]

_TRIGGER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in TRIGGER_WORDS) + r")\b",
    re.IGNORECASE,
)


def contains_trigger_word(content: str) -> bool:
    return bool(_TRIGGER_PATTERN.search(content))


class Chicken_Reactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if contains_trigger_word(message.content):
            await message.add_reaction(random.choice(REACTION_EMOJIS))


def setup(bot):
    bot.add_cog(Chicken_Reactions(bot))
