import re

from discord.ext import commands

from shared.emojis import CHICKEN_EMOJI, CHIKBOT_EMOJI, EGG_EMOJI, HATCHLING_EMOJI, ROOSTER_EMOJI

SUBSTRING_WORD_EMOJIS = {
    "eggs": EGG_EMOJI,
    "cock": ROOSTER_EMOJI,
    "rooster": ROOSTER_EMOJI,
    "scared": HATCHLING_EMOJI,
    "coward": HATCHLING_EMOJI,
    "chicken": CHICKEN_EMOJI,
    "corp": CHICKEN_EMOJI,
    "cluck": CHICKEN_EMOJI,
    "bawk": CHICKEN_EMOJI,
    "feathers": CHICKEN_EMOJI,
    "poultry": CHICKEN_EMOJI,
    "peck": CHICKEN_EMOJI,
}

WHOLE_WORD_EMOJIS = {
    "egg": EGG_EMOJI,
    "bot": CHIKBOT_EMOJI,
    "ai": CHIKBOT_EMOJI,
}

_WHOLE_WORD_PATTERNS = {
    word: re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
    for word in WHOLE_WORD_EMOJIS
}


def matching_emojis(content: str) -> set:
    lowered = content.lower()
    emojis = {emoji for word, emoji in SUBSTRING_WORD_EMOJIS.items() if word in lowered}
    emojis |= {
        WHOLE_WORD_EMOJIS[word]
        for word, pattern in _WHOLE_WORD_PATTERNS.items()
        if pattern.search(content)
    }
    return emojis


class Chicken_Reactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        for emoji in matching_emojis(message.content):
            await message.add_reaction(emoji)


def setup(bot):
    bot.add_cog(Chicken_Reactions(bot))
