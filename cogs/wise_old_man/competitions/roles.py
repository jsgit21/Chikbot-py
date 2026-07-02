import os

import discord


async def swap_winner_roles(guild, botw_discord_id, sotw_discord_id):
    """Strip all winner roles from current holders and assign to new winners.

    botw_discord_id / sotw_discord_id are Discord user IDs (int) or None.
    Returns a list of warning strings for any roles that could not be assigned.
    """
    def _get_role(env_key):
        val = os.getenv(env_key)
        return guild.get_role(int(val)) if val else None

    sotw_role = _get_role('SOTW_WINNER_ROLE')
    botw_role = _get_role('BOTW_WINNER_ROLE')
    comp_role = _get_role('COMPETITION_WINNER_ROLE')
    all_winner_roles = [r for r in (sotw_role, botw_role, comp_role) if r]

    warnings = []

    for role in all_winner_roles:
        for member in list(role.members):
            await member.remove_roles(role, reason='Competition cycle ended')

    if botw_discord_id:
        member = guild.get_member(botw_discord_id)
        if member:
            to_add = [r for r in (botw_role, comp_role) if r]
            if to_add:
                await member.add_roles(*to_add, reason='BOTW winner')
        else:
            warnings.append(f'BOTW winner (id {botw_discord_id}) not found in guild — roles not assigned.')
    else:
        warnings.append('BOTW winner has no Discord link — BOTW roles not assigned.')

    if sotw_discord_id:
        member = guild.get_member(sotw_discord_id)
        if member:
            to_add = [r for r in (sotw_role, comp_role) if r]
            if to_add:
                await member.add_roles(*to_add, reason='SOTW winner')
        else:
            warnings.append(f'SOTW winner (id {sotw_discord_id}) not found in guild — roles not assigned.')
    else:
        warnings.append('SOTW winner has no Discord link — SOTW roles not assigned.')

    return warnings
