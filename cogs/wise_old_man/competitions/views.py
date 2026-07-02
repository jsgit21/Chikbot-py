import asyncio
import os

import discord

from . import db as comp_db
from . import announcements, metrics, roles, wom_api
from ..identity import db as identity_db
from .scheduling import to_wom_iso


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


# -----------------------------------------------------------------------------
# /competition create: preview -> confirm -> create on WOM
# -----------------------------------------------------------------------------

class ConfirmCreateButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label='Confirm & Create', style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        payload = self.view.payload

        try:
            botw_resp = await asyncio.to_thread(
                wom_api.create_competition,
                payload['botw']['title'], payload['botw']['metric'],
                to_wom_iso(payload['starts_at']), to_wom_iso(payload['ends_at']),
            )
            sotw_resp = await asyncio.to_thread(
                wom_api.create_competition,
                payload['sotw']['title'], payload['sotw']['metric'],
                to_wom_iso(payload['starts_at']), to_wom_iso(payload['ends_at']),
            )
        except Exception as exc:
            await interaction.followup.send(
                f'Failed to create competitions on WOM: {exc}\n'
                'Check the WOM group manually before retrying — one competition may have '
                'already been created.',
                ephemeral=True,
            )
            return

        cycle_id = await asyncio.to_thread(
            comp_db.insert_cycle, payload['starts_at'], payload['ends_at'], 'planned'
        )
        await asyncio.to_thread(
            comp_db.upsert_competition,
            botw_resp['competition']['id'], cycle_id, 'botw',
            payload['botw']['metric'], payload['botw']['title'],
            payload['starts_at'], payload['ends_at'],
            botw_resp['verificationCode'], payload['botw']['picker_user_id'],
        )
        await asyncio.to_thread(
            comp_db.upsert_competition,
            sotw_resp['competition']['id'], cycle_id, 'sotw',
            payload['sotw']['metric'], payload['sotw']['title'],
            payload['starts_at'], payload['ends_at'],
            sotw_resp['verificationCode'], payload['sotw']['picker_user_id'],
        )

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)

        kickoff_text = announcements.build_kickoff_post(
            payload['starts_at'], payload['ends_at'], payload['botw'], payload['sotw']
        )
        draft = (
            '**[DRAFT] Kickoff Announcement — Pending Mod Approval**\n\n'
            f'{kickoff_text}\n\n'
            '-# Click **Approve & Post** to publish to the announcements channel.'
        )
        mod_channel = interaction.client.get_channel(int(os.getenv('MODERATOR_CHANNEL')))
        await mod_channel.send(draft, view=KickoffApprovalView())

        await interaction.followup.send(
            'Both competitions created on WOM. Kickoff post drafted for approval.',
            ephemeral=True,
        )


class CancelCreateButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label='Cancel', style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction):
        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message('Cancelled — nothing was created.', ephemeral=True)


class ConfirmCreateView(discord.ui.View):
    """Preview -> confirm gate for /competition create.

    Not persistent: the mod is expected to confirm or cancel in the same
    session the preview was posted, so a timeout (rather than a custom_id
    surviving restarts) is enough here.

    payload: {
        'starts_at': datetime, 'ends_at': datetime,  # naive UTC
        'botw': {'metric': slug, 'metric_display': str, 'title': str,
                  'picker_user_id': int or None, 'picker_text': str},
        'sotw': {...same shape...},
    }
    """

    def __init__(self, payload):
        super().__init__(timeout=300)
        self.payload = payload
        self.add_item(ConfirmCreateButton())
        self.add_item(CancelCreateButton())


# -----------------------------------------------------------------------------
# Kickoff announcement approval gate
# -----------------------------------------------------------------------------

def _picker_mention(picker_user_id):
    return f'<@{picker_user_id}>' if picker_user_id else 'the group'


class ApproveKickoffButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='Approve & Post',
            style=discord.ButtonStyle.green,
            custom_id='comp_approve_kickoff',
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        planned = await asyncio.to_thread(comp_db.get_planned_cycles)
        if not planned:
            await interaction.followup.send(
                'No pending kickoff found — it may have already been approved or dismissed.',
                ephemeral=True,
            )
            return

        cycle = planned[0]
        comps = await asyncio.to_thread(comp_db.get_competitions_for_cycle, cycle['id'])
        botw_row = next((c for c in comps if c['type'] == 'botw'), None)
        sotw_row = next((c for c in comps if c['type'] == 'sotw'), None)

        if not botw_row or not sotw_row:
            await interaction.followup.send(
                'Competition data is incomplete in the DB. Cannot approve.',
                ephemeral=True,
            )
            return

        def _pick(row):
            return {
                'title': row['title'],
                'metric_display': metrics.display_name(row['type'], row['metric']),
                'picker_text': _picker_mention(row['picker_user_id']),
            }

        text = announcements.build_kickoff_post(
            cycle['starts_at'], cycle['ends_at'], _pick(botw_row), _pick(sotw_row)
        )

        ann_channel_id = os.getenv('ANNOUNCEMENTS_CHANNEL')
        if not ann_channel_id:
            await interaction.followup.send(
                'ANNOUNCEMENTS_CHANNEL is not set. Set the env var and redeploy.',
                ephemeral=True,
            )
            return

        ann_channel = interaction.client.get_channel(int(ann_channel_id))
        await ann_channel.send(text)

        await asyncio.to_thread(comp_db.set_cycle_status, cycle['id'], 'active')

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        await interaction.followup.send('Kickoff post published.', ephemeral=True)


class DismissKickoffButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='Dismiss',
            style=discord.ButtonStyle.red,
            custom_id='comp_dismiss_kickoff',
        )

    async def callback(self, interaction: discord.Interaction):
        planned = await asyncio.to_thread(comp_db.get_planned_cycles)
        if planned:
            await asyncio.to_thread(comp_db.set_cycle_status, planned[0]['id'], 'active')

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message('Dismissed.', ephemeral=True)


class KickoffApprovalView(discord.ui.View):
    """Persistent approval gate for the kickoff announcement.

    The bot must call bot.add_view(KickoffApprovalView()) in on_ready to
    re-register the handler after a restart.
    """

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ApproveKickoffButton())
        self.add_item(DismissKickoffButton())
