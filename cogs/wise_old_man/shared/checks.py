import os

import discord

# Hard-coded to match the existing check in wise_old_man.py
MODERATOR_ROLE_ID = 360455451852406797


def is_moderator(ctx):
    mod_role = discord.utils.get(ctx.author.roles, name='Moderator', id=MODERATOR_ROLE_ID)
    return mod_role is not None


def in_moderator_channel(ctx):
    # Read lazily so importing this module never depends on env load order.
    return ctx.channel.id == int(os.getenv('MODERATOR_CHANNEL'))


def moderator_command(ctx):
    return is_moderator(ctx) and in_moderator_channel(ctx)
