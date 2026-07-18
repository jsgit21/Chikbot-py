import os

from . import types


def _get_role(guild, env_key):
    val = os.getenv(env_key)
    return guild.get_role(int(val)) if val else None


def _holds_other_type_role(guild, member, comp_type):
    """True if member still holds a different type's specific winner role."""
    for other in types.TYPES.values():
        if other.key == comp_type.key:
            continue
        other_role = _get_role(guild, other.winner_role_env)
        if other_role and member in other_role.members:
            return True
    return False


async def assign_winner_role(guild, discord_id, comp_type):
    """Strip comp_type's role from its current holders and assign it (plus the
    shared COMPETITION_WINNER_ROLE) to the new winner.

    discord_id is the winning Discord user's id (int) or None.
    Returns a list of warning strings for anything that could not be assigned.
    """
    comp_role = _get_role(guild, comp_type.winner_role_env)
    shared_role = _get_role(guild, 'COMPETITION_WINNER_ROLE')

    warnings = []

    if comp_role:
        for member in list(comp_role.members):
            await member.remove_roles(comp_role, reason=f'{comp_type.display_name} cycle ended')
            if shared_role and not _holds_other_type_role(guild, member, comp_type):
                await member.remove_roles(shared_role, reason=f'{comp_type.display_name} cycle ended')

    if discord_id:
        member = guild.get_member(discord_id)
        if member:
            to_add = [r for r in (comp_role, shared_role) if r]
            if to_add:
                await member.add_roles(*to_add, reason=f'{comp_type.display_name} winner')
        else:
            warnings.append(
                f'{comp_type.display_name} winner (id {discord_id}) not found in guild — roles not assigned.'
            )
    else:
        warnings.append(f'{comp_type.display_name} winner has no Discord link — roles not assigned.')

    return warnings
