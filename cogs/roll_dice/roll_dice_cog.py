import discord
from discord.ext import commands
from . import dice_art


class RollDice(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name='roll-dice', description='Roll a die and see the result as ASCII art')
    async def roll_dice(self, ctx,
                        number_of_sides: discord.Option(int, 'Number of sides on the die', required=False, default=20, min_value=2, max_value=100),
                        modifier: discord.Option(int, 'Number to add or subtract from the roll', required=False, default=0, min_value=-100, max_value=100)):
        result = dice_art.roll(number_of_sides)
        art = dice_art.render(number_of_sides, result)

        if modifier:
            total = result + modifier
            summary = f'🎲 You rolled a **{result}** ({modifier:+d}) on a d{number_of_sides} = **{total}**!'
        else:
            summary = f'🎲 You rolled a **{result}** on a d{number_of_sides}!'

        await ctx.respond(f'{summary}\n```\n{art}\n```')


def setup(bot):
    bot.add_cog(RollDice(bot))
