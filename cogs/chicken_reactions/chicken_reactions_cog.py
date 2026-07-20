import random
import re

from discord.ext import commands

from shared.emojis import CHICKEN_EMOJI, CHIKBOT_EMOJI, EGG_EMOJI, HATCHLING_EMOJI, ROOSTER_EMOJI

def _flatten(emoji_words: dict) -> dict:
    flat = {}
    for emoji, words in emoji_words.items():
        for word in words:
            flat[word] = emoji
    return flat


SUBSTRING_EMOJI_WORDS = {
    EGG_EMOJI: ["eggs"],
    ROOSTER_EMOJI: ["cock", "rooster"],
    HATCHLING_EMOJI: ["scared", "coward"],
    CHICKEN_EMOJI: ["chicken", "cluck", "bawk", "feathers", "poultry", "peck"],
}
SUBSTRING_WORD_EMOJIS = _flatten(SUBSTRING_EMOJI_WORDS)

WHOLE_EMOJI_WORDS = {
    EGG_EMOJI: ["egg"],
    CHIKBOT_EMOJI: ["bot", "ai"],
    CHICKEN_EMOJI: ["corp", "corporeal beast", "kree", "kree'arra"],
}
WHOLE_WORD_EMOJIS = _flatten(WHOLE_EMOJI_WORDS)

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
        emojis = matching_emojis(message.content)
        if emojis:
            await message.add_reaction(random.choice(list(emojis)))


def setup(bot):
    bot.add_cog(Chicken_Reactions(bot))
