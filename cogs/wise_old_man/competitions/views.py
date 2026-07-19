import asyncio
import os

import discord

from . import db as comp_db
from . import announcements, metrics, roles, types, winners, wom_api
from ..shared import checks
from .scheduling import to_wom_iso


class ApproveButton(discord.ui.Button):
    def __init__(self, competition_id):
        super().__init__(
            label='Approve & Post',
            style=discord.ButtonStyle.green,
            custom_id=f'comp_approve_results:{competition_id}',
        )
        self.competition_id = competition_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        claimed = await asyncio.to_thread(comp_db.claim_competition_for_announcing, self.competition_id)
        if not claimed:
            await interaction.followup.send(
                'This competition is already being processed or was already approved.',
            )
            return

        try:
            detail = await asyncio.to_thread(wom_api.get_competition, self.competition_id)
        except Exception as exc:
            await interaction.followup.send(f'WOM API error re-fetching competition: {exc}')
            return

        comp_type = types.infer_type_from_title(detail.get('title', ''))
        if comp_type is None:
            await interaction.followup.send(
                f'Competition title "{detail.get("title")}" no longer matches a known competition type.'
            )
            return

        winner = winners.resolve_winner(detail)
        text = announcements.build_result_post(comp_type, winner)

        ann_channel_id = os.getenv('ANNOUNCEMENTS_CHANNEL')
        if not ann_channel_id:
            await interaction.followup.send(
                'ANNOUNCEMENTS_CHANNEL is not set. Set the env var and redeploy.',
            )
            return

        ann_channel = interaction.client.get_channel(int(ann_channel_id))
        if ann_channel is None:
            await interaction.followup.send(
                f'Announcements channel {ann_channel_id} not found — check ANNOUNCEMENTS_CHANNEL.',
            )
            return

        await ann_channel.send(text)

        guild = interaction.guild
        discord_id = winner['discord_user_id'] if winner else None
        try:
            role_warnings = await roles.assign_winner_role(guild, discord_id, comp_type)
        except Exception as exc:
            role_warnings = [f'Role assignment failed: {exc}']

        await asyncio.to_thread(comp_db.set_results_status, self.competition_id, 'announced')

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)

        reply = 'Results posted and roles assigned.'
        if role_warnings:
            reply += '\n\n**Role warnings:**\n' + '\n'.join(f'- {w}' for w in role_warnings)
        await interaction.followup.send(reply)


class DismissButton(discord.ui.Button):
    def __init__(self, competition_id):
        super().__init__(
            label='Dismiss',
            style=discord.ButtonStyle.red,
            custom_id=f'comp_dismiss_results:{competition_id}',
        )
        self.competition_id = competition_id

    async def callback(self, interaction: discord.Interaction):
        claimed = await asyncio.to_thread(comp_db.claim_competition_for_announcing, self.competition_id)
        if not claimed:
            await interaction.response.send_message(
                'This competition is already being processed or was already approved.'
            )
            return

        await asyncio.to_thread(comp_db.set_results_status, self.competition_id, 'deferred')

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message('Dismissed.')


class ResultsApprovalView(discord.ui.View):
    """Persistent approval gate for one competition's results.

    Embeds competition_id in each button's custom_id so a click always
    resolves to this specific competition rather than "whichever is newest" —
    multiple drafts can be outstanding at once. The bot must call
    bot.add_view(ResultsApprovalView(competition_id)) in on_ready for every
    still-drafted competition to re-register the handler after a restart.
    """

    def __init__(self, competition_id):
        super().__init__(timeout=None)
        self.add_item(ApproveButton(competition_id))
        self.add_item(DismissButton(competition_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not checks.moderator_interaction(interaction):
            await interaction.response.send_message(
                'Moderators only, in the mod channel.', ephemeral=True)
            return False
        return True


# -----------------------------------------------------------------------------
# /competition create: preview -> confirm -> create on WOM
# -----------------------------------------------------------------------------

class ConfirmCreateButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label='Confirm & Create', style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        payload = self.view.payload

        cycle_id = payload['cycle_id']
        if cycle_id is None:
            cycle_id = await asyncio.to_thread(
                comp_db.insert_cycle, payload['starts_at'], payload['ends_at'], 'planned'
            )

        async def _ensure_side(side):
            """Create side on WOM and persist it, unless a resumed cycle already has it."""
            if side['existing_competition_id']:
                return None

            resp = await asyncio.to_thread(
                wom_api.create_competition,
                side['title'], side['metric'],
                to_wom_iso(payload['starts_at']), to_wom_iso(payload['ends_at']),
            )
            await asyncio.to_thread(
                comp_db.ensure_competition_row,
                resp['competition']['id'], cycle_id,
                resp['verificationCode'], side['nominator_user_id'],
            )
            return resp

        try:
            await _ensure_side(payload['botw'])
        except Exception as exc:
            await interaction.followup.send(
                f'Failed to create the BOTW competition on WOM: {exc}\n'
                'Nothing was created — rerun `/competition create` to retry.',
                ephemeral=True,
            )
            return

        try:
            await _ensure_side(payload['sotw'])
        except Exception as exc:
            await interaction.followup.send(
                f'BOTW was created on WOM, but the SOTW competition failed: {exc}\n'
                'Rerun `/competition create` with the same options to resume — '
                'BOTW will not be duplicated.',
                ephemeral=True,
            )
            return

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
        mod_channel_id = checks.moderator_channel_id()
        mod_channel = interaction.client.get_channel(mod_channel_id)
        if mod_channel is None:
            await interaction.followup.send(
                f'Moderator channel {mod_channel_id} not found — check MODERATOR_CHANNEL. '
                'Both competitions were created on WOM; the kickoff post still needs to be sent.',
                ephemeral=True,
            )
            return
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
                  'nominator_user_id': int or None, 'nominator_text': str},
        'sotw': {...same shape...},
    }
    """

    def __init__(self, payload):
        super().__init__(timeout=300)
        self.payload = payload
        self.add_item(ConfirmCreateButton())
        self.add_item(CancelCreateButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not checks.moderator_interaction(interaction):
            await interaction.response.send_message(
                'Moderators only, in the mod channel.', ephemeral=True)
            return False
        return True


# -----------------------------------------------------------------------------
# Kickoff announcement approval gate
# -----------------------------------------------------------------------------

def _nominator_mention(nominator_user_id):
    return f'<@{nominator_user_id}>' if nominator_user_id else 'the group'


class ApproveKickoffButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='Approve & Post',
            style=discord.ButtonStyle.green,
            custom_id='comp_approve_kickoff',
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        planned = await asyncio.to_thread(comp_db.get_planned_cycles)
        if not planned:
            await interaction.followup.send(
                'No pending kickoff found — it may have already been approved or dismissed.',
            )
            return

        cycle = planned[0]

        claimed = await asyncio.to_thread(comp_db.claim_cycle_for_publishing, cycle['id'])
        if not claimed:
            await interaction.followup.send(
                'This cycle is already being processed or was already approved.',
            )
            return

        comps = await asyncio.to_thread(comp_db.get_competitions_for_cycle, cycle['id'])
        by_type = {}
        for row in comps:
            try:
                detail = await asyncio.to_thread(wom_api.get_competition, row['competition_id'])
            except Exception as exc:
                await interaction.followup.send(
                    f'WOM API error fetching competition {row["competition_id"]}: {exc}'
                )
                return
            comp_type = types.infer_type_from_title(detail.get('title', ''))
            if comp_type:
                by_type[comp_type.key] = (row, detail)

        if 'botw' not in by_type or 'sotw' not in by_type:
            await interaction.followup.send(
                'Competition data is incomplete in the DB. Cannot approve.',
            )
            return

        def _pick(comp_type_key):
            row, detail = by_type[comp_type_key]
            return {
                'title': detail['title'],
                'metric_display': metrics.display_name(comp_type_key, detail['metric']),
                'nominator_text': _nominator_mention(row['nominator_user_id']),
            }

        text = announcements.build_kickoff_post(
            cycle['starts_at'], cycle['ends_at'], _pick('botw'), _pick('sotw')
        )

        ann_channel_id = os.getenv('ANNOUNCEMENTS_CHANNEL')
        if not ann_channel_id:
            await interaction.followup.send(
                'ANNOUNCEMENTS_CHANNEL is not set. Set the env var and redeploy.',
            )
            return

        ann_channel = interaction.client.get_channel(int(ann_channel_id))
        if ann_channel is None:
            await interaction.followup.send(
                f'Announcements channel {ann_channel_id} not found — check ANNOUNCEMENTS_CHANNEL.',
            )
            return

        await ann_channel.send(text)

        await asyncio.to_thread(comp_db.set_cycle_status, cycle['id'], 'active')

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        await interaction.followup.send('Kickoff post published.')


class DismissKickoffButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='Dismiss',
            style=discord.ButtonStyle.red,
            custom_id='comp_dismiss_kickoff',
        )

    async def callback(self, interaction: discord.Interaction):
        planned = await asyncio.to_thread(comp_db.get_planned_cycles)
        if not planned:
            await interaction.response.send_message(
                'No pending kickoff found — it may have already been approved or dismissed.'
            )
            return

        cycle_id = planned[0]['id']
        claimed = await asyncio.to_thread(comp_db.claim_cycle_for_publishing, cycle_id)
        if not claimed:
            await interaction.response.send_message(
                'This cycle is already being processed or was already approved.'
            )
            return

        await asyncio.to_thread(comp_db.set_cycle_status, cycle_id, 'active')

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message('Dismissed.')


class KickoffApprovalView(discord.ui.View):
    """Persistent approval gate for the kickoff announcement.

    The bot must call bot.add_view(KickoffApprovalView()) in on_ready to
    re-register the handler after a restart.
    """

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ApproveKickoffButton())
        self.add_item(DismissKickoffButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not checks.moderator_interaction(interaction):
            await interaction.response.send_message(
                'Moderators only, in the mod channel.', ephemeral=True)
            return False
        return True
