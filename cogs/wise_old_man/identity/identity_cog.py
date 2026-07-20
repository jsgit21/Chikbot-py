import asyncio
import discord
import database.db_methods as db_methods

from discord.ext import commands
from ..shared import checks
from . import db as identity_db


def _chunk_lines(lines, limit=1800):
    # Pack lines into messages under Discord's 2000-char limit, like
    # wise_old_man.format_output does for the rank report.
    chunks = []
    buffer = []
    for line in lines:
        candidate = '\n'.join(buffer + [line])
        if len(candidate) > limit and buffer:
            chunks.append('\n'.join(buffer))
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        chunks.append('\n'.join(buffer))
    return chunks


class Identity(commands.Cog):

    wom = discord.SlashCommandGroup('wom', 'Link RuneScape names to Discord members')

    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.respond(
                'This command is for moderators in the mod channel only.',
                ephemeral=True,
            )
        else:
            raise error

    @wom.command(description='Link a RuneScape name to a Discord member')
    @commands.check(checks.moderator_command)
    async def link(self, ctx,
                   rsn: discord.Option(str, 'RuneScape name as it appears in WOM', required=True),
                   member: discord.Option(discord.Member, 'Discord member to link', required=True),
                   alias: discord.Option(str, 'Conversational alias (e.g. mayo)', required=False) = None):
        # Ensure the user row exists so the wom_link foreign key is satisfied.
        await asyncio.to_thread(db_methods.register_user, member)
        linked = await asyncio.to_thread(identity_db.link_rsn, rsn, member.id)

        if linked is None:
            await ctx.respond(f'`{rsn}` is not in the WOM group. Sync the group first.')
            return

        if alias:
            await asyncio.to_thread(identity_db.set_preferred_alias, member.id, alias)

        message = f'Linked `{linked["rsn"]}` to {member.mention}'
        if alias:
            message += f' (alias: **{alias}**)'
        await ctx.respond(message)

    @wom.command(description='Unlink a RuneScape name')
    @commands.check(checks.moderator_command)
    async def unlink(self, ctx,
                     rsn: discord.Option(str, 'RuneScape name to unlink', required=True)):
        removed = await asyncio.to_thread(identity_db.unlink_rsn, rsn)
        if removed:
            await ctx.respond(f'Unlinked `{rsn}`')
        else:
            await ctx.respond(f'No link found for `{rsn}`')

    @wom.command(description='List WOM members with no Discord link')
    @commands.check(checks.moderator_command)
    async def unlinked(self, ctx):
        members = await asyncio.to_thread(identity_db.get_unlinked_members)
        if not members:
            await ctx.respond('All WOM members are linked. 🎉')
            return

        lines = ['__Unlinked WOM members__:'] + [f'`{m["rsn"]}`' for m in members]
        chunks = _chunk_lines(lines)

        await ctx.respond(chunks[0])
        for chunk in chunks[1:]:
            await ctx.send_followup(chunk)

    @wom.command(description='Show link info for an RSN or a member')
    @commands.check(checks.moderator_command)
    async def whois(self, ctx,
                    rsn: discord.Option(str, 'RuneScape name', required=False) = None,
                    member: discord.Option(discord.Member, 'Discord member', required=False) = None):
        if rsn:
            row = await asyncio.to_thread(identity_db.whois_rsn, rsn)
            if row is None:
                await ctx.respond(f'No link found for `{rsn}`')
                return
            alias = f' (alias: **{row["preferred_alias"]}**)' if row['preferred_alias'] else ''
            await ctx.respond(f'`{row["rsn"]}` is linked to <@{row["user_id"]}>{alias}')
            return

        if member:
            rows = await asyncio.to_thread(identity_db.whois_user, member.id)
            if not rows:
                await ctx.respond(f'{member.mention} has no linked RSNs')
                return
            names = ', '.join(f'`{r["rsn"]}`' for r in rows)
            alias = rows[0]['preferred_alias']
            alias_text = f' (alias: **{alias}**)' if alias else ''
            await ctx.respond(f'{member.mention}{alias_text} is linked to: {names}')
            return

        await ctx.respond('Provide either an `rsn` or a `member`.')

    @wom.command(description="Set a member's conversational alias")
    @commands.check(checks.moderator_command)
    async def alias(self, ctx,
                    member: discord.Option(discord.Member, 'Discord member', required=True),
                    alias: discord.Option(str, 'Conversational alias (e.g. mayo)', required=True)):
        await asyncio.to_thread(db_methods.register_user, member)
        await asyncio.to_thread(identity_db.set_preferred_alias, member.id, alias)
        await ctx.respond(f'Alias for {member.mention} set to **{alias}**')

    # ------------------------------------------------------------------
    # User-facing self-service commands (no mod gate)
    # ------------------------------------------------------------------

    @wom.command(description='Link a RuneScape name to your own Discord account')
    async def claim(self, ctx,
                    rsn: discord.Option(str, 'Your RuneScape name as it appears in WOM', required=True)):
        await asyncio.to_thread(db_methods.register_user, ctx.author)
        status, member = await asyncio.to_thread(identity_db.claim_rsn, rsn, ctx.author.id)

        if status == 'not_in_group':
            await ctx.respond(
                f'`{rsn}` is not in the WOM group. Check the spelling or ask a mod.',
                ephemeral=True,
            )
        elif status == 'already_yours':
            await ctx.respond(
                f'`{member["rsn"]}` is already linked to your account.',
                ephemeral=True,
            )
        elif status == 'already_claimed':
            await ctx.respond(
                f'`{member["rsn"]}` is already linked to another member. '
                'If this is your account, ask a moderator to resolve it.',
                ephemeral=True,
            )
        else:
            await ctx.respond(f'Linked `{member["rsn"]}` to your account.')

    @wom.command(description='Remove a RuneScape name from your Discord account')
    async def unclaim(self, ctx,
                      rsn: discord.Option(str, 'RuneScape name to remove from your account', required=True)):
        status = await asyncio.to_thread(identity_db.unclaim_rsn, rsn, ctx.author.id)

        if status == 'not_in_group':
            await ctx.respond(f'`{rsn}` is not in the WOM group.', ephemeral=True)
        elif status == 'not_linked':
            await ctx.respond(f'`{rsn}` has no Discord link to remove.', ephemeral=True)
        elif status == 'not_yours':
            await ctx.respond(f'`{rsn}` is not linked to your account.', ephemeral=True)
        else:
            await ctx.respond(f'Removed `{rsn}` from your linked accounts.', ephemeral=True)

    @wom.command(description='Show the RuneScape names linked to your account')
    async def myrsns(self, ctx):
        rows = await asyncio.to_thread(identity_db.whois_user, ctx.author.id)
        if not rows:
            await ctx.respond(
                'You have no linked RSNs. Use `/wom claim <rsn>` to add one.',
                ephemeral=True,
            )
            return
        names = ', '.join(f'`{r["rsn"]}`' for r in rows)
        alias = rows[0]['preferred_alias']
        alias_text = f' (alias: **{alias}**)' if alias else ''
        await ctx.respond(f'Your linked RSNs{alias_text}: {names}', ephemeral=True)


def setup(bot):
    bot.add_cog(Identity(bot))
