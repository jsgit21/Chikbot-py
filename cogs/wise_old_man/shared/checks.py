import os

import discord

# Hard-coded to match the existing check in wise_old_man.py
MODERATOR_ROLE_ID = 360455451852406797


def is_moderator(ctx):
    mod_role = discord.utils.get(ctx.author.roles, name='Moderator', id=MODERATOR_ROLE_ID)
    return mod_role is not None


def moderator_channel_id():
    return int(os.getenv('MODERATOR_CHANNEL'))


def in_moderator_channel(ctx):
    return ctx.channel.id == moderator_channel_id()


def moderator_command(ctx):
    return is_moderator(ctx) and in_moderator_channel(ctx)


def is_moderator_interaction(interaction):
    member = interaction.user
    if not hasattr(member, 'roles'):   # not in a guild
        return False
    return discord.utils.get(member.roles, name='Moderator', id=MODERATOR_ROLE_ID) is not None


def in_moderator_channel_interaction(interaction):
    return interaction.channel_id == moderator_channel_id()


def moderator_interaction(interaction):
    return is_moderator_interaction(interaction) and in_moderator_channel_interaction(interaction)
