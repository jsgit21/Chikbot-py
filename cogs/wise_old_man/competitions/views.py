import asyncio
import os

import discord

from . import db as comp_db
from . import roles, announcements
from ..identity import db as identity_db


class ApproveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='Approve & Post',
            style=discord.ButtonStyle.green,
            custom_id='comp_approve_results',
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        pending = await asyncio.to_thread(comp_db.get_pending_cycles)
        if not pending:
            await interaction.followup.send(
                'No pending cycle found — it may have already been approved or dismissed.',
                ephemeral=True,
            )
            return

        cycle = pending[0]
        comps = await asyncio.to_thread(comp_db.get_competitions_for_cycle, cycle['id'])
        botw_row = next((c for c in comps if c['type'] == 'botw'), None)
        sotw_row = next((c for c in comps if c['type'] == 'sotw'), None)

        if not botw_row or not sotw_row:
            await interaction.followup.send(
                'Competition data is incomplete in the DB. Cannot approve.',
                ephemeral=True,
            )
            return

        async def _build_winner(row):
            if not row['winner_wom_user_id']:
                return None
            rsn = await asyncio.to_thread(comp_db.get_rsn_for_wom_id, row['winner_wom_user_id'])
            identity = await asyncio.to_thread(
                identity_db.discord_user_for_wom_id, row['winner_wom_user_id']
            )
            return {
                'competition_id': row['competition_id'],
                'wom_user_id': row['winner_wom_user_id'],
                'rsn': rsn or 'unknown',
                'gained': row['winner_gained'],
                'discord_user_id': identity['user_id'] if identity else None,
                'alias': identity['preferred_alias'] if identity else None,
            }

        botw_winner = await _build_winner(botw_row)
        sotw_winner = await _build_winner(sotw_row)

        text = announcements.build_results_post(botw_winner, sotw_winner)

        ann_channel_id = os.getenv('ANNOUNCEMENTS_CHANNEL')
        if not ann_channel_id:
            await interaction.followup.send(
                'ANNOUNCEMENTS_CHANNEL is not set. Set the env var and redeploy.',
                ephemeral=True,
            )
            return

        ann_channel = interaction.client.get_channel(int(ann_channel_id))
        await ann_channel.send(text)

        guild = interaction.guild
        botw_did = botw_winner['discord_user_id'] if botw_winner else None
        sotw_did = sotw_winner['discord_user_id'] if sotw_winner else None
        role_warnings = await roles.swap_winner_roles(guild, botw_did, sotw_did)

        await asyncio.to_thread(comp_db.mark_results_posted, botw_row['competition_id'])
        await asyncio.to_thread(comp_db.mark_results_posted, sotw_row['competition_id'])
        await asyncio.to_thread(comp_db.set_cycle_status, cycle['id'], 'announced')

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)

        reply = 'Results posted and roles swapped.'
        if role_warnings:
            reply += '\n\n**Role warnings:**\n' + '\n'.join(f'- {w}' for w in role_warnings)
        await interaction.followup.send(reply, ephemeral=True)


class DismissButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='Dismiss',
            style=discord.ButtonStyle.red,
            custom_id='comp_dismiss_results',
        )

    async def callback(self, interaction: discord.Interaction):
        pending = await asyncio.to_thread(comp_db.get_pending_cycles)
        if pending:
            await asyncio.to_thread(comp_db.set_cycle_status, pending[0]['id'], 'announced')

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message('Dismissed.', ephemeral=True)


class ResultsApprovalView(discord.ui.View):
    """Persistent approval gate for competition results.

    Uses stable custom_ids so the buttons survive bot restarts. The bot must
    call bot.add_view(ResultsApprovalView()) in on_ready to re-register the
    handler after a restart.
    """

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ApproveButton())
        self.add_item(DismissButton())
