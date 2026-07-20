import asyncio
import datetime
import os

import discord

from shared import tz
from . import db as comp_db
from . import announcements, cycle_lookup, metrics, raid_pairs, roles, types, winners, wom_api
from ..shared import checks
from .scheduling import to_wom_iso


def to_local_dt(iso_str):
    """Convert a WOM UTC ISO-8601 string to a naive ET (server-local) datetime."""
    utc_dt = datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    return utc_dt.astimezone(tz.ET).replace(tzinfo=None)


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

        pair = raid_pairs.pair_for_metric(detail.get('metric'))
        sibling_id = None
        if pair is not None:
            try:
                competitions = await asyncio.to_thread(wom_api.list_group_competitions)
                sibling_detail = await raid_pairs.find_sibling(detail, competitions)
            except Exception as exc:
                await interaction.followup.send(f'WOM API error while locating the raid-pair sibling: {exc}')
                return
            if sibling_detail is None:
                await interaction.followup.send(
                    f"This is one half of a {pair.display_name} raid pair, but its sibling competition "
                    "couldn't be found on WOM right now. Try again shortly, or resolve it manually if it looks orphaned."
                )
                return
            sibling_id = sibling_detail['id']
            base_detail, hard_detail = (
                (detail, sibling_detail) if detail['metric'] == pair.base_metric else (sibling_detail, detail)
            )
            winner = winners.resolve_paired_winner(pair, base_detail, hard_detail)
            text = announcements.build_raid_pair_result_post(comp_type, pair, winner)
        else:
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
        if sibling_id is not None:
            # _handle_raid_pair_candidate always drafts both halves together, so sibling_id
            # is expected to already be 'drafted' here.
            sibling_claimed = await asyncio.to_thread(comp_db.claim_competition_for_announcing, sibling_id)
            if not sibling_claimed:
                role_warnings = list(role_warnings) + [
                    f'Raid-pair sibling competition {sibling_id} was not in the expected '
                    "'drafted' state when approving — check its results_status manually."
                ]
            await asyncio.to_thread(comp_db.set_results_status, sibling_id, 'announced')

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

        sibling_warning = None
        try:
            detail = await asyncio.to_thread(wom_api.get_competition, self.competition_id)
            pair = raid_pairs.pair_for_metric(detail.get('metric'))
            if pair is not None:
                competitions = await asyncio.to_thread(wom_api.list_group_competitions)
                sibling_detail = await raid_pairs.find_sibling(detail, competitions)
                if sibling_detail is not None:
                    await asyncio.to_thread(comp_db.claim_competition_for_announcing, sibling_detail['id'])
                    await asyncio.to_thread(comp_db.set_results_status, sibling_detail['id'], 'deferred')
                else:
                    sibling_warning = (
                        f'Note: this was one half of a {pair.display_name} raid pair, but its sibling '
                        "couldn't be located to dismiss alongside it — check its status manually."
                    )
        except Exception as exc:
            sibling_warning = f'Note: failed to check/dismiss the raid-pair sibling: {exc}'

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        reply = 'Dismissed.'
        if sibling_warning:
            reply += f'\n\n-# {sibling_warning}'
        await interaction.response.send_message(reply)


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
        sides = payload['sides']

        cycle_id = payload['cycle_id']
        if cycle_id is None and len(sides) > 1:
            cycle_id = await asyncio.to_thread(
                comp_db.insert_cycle, payload['starts_at'], payload['ends_at'], 'planned'
            )

        kickoff_status = 'drafted' if len(sides) == 1 else None

        async def _create_and_persist(title, metric, nominator_user_id, this_kickoff_status):
            resp = await asyncio.to_thread(
                wom_api.create_competition, title, metric,
                to_wom_iso(payload['starts_at']), to_wom_iso(payload['ends_at']),
            )
            await asyncio.to_thread(
                comp_db.ensure_competition_row, resp['competition']['id'], cycle_id,
                resp['verificationCode'], nominator_user_id, this_kickoff_status,
            )
            return resp['competition']['id']

        created = []  # [(label_dict, competition_id), ...] -- one entry per underlying WOM competition
        try:
            for side in sides:
                units = side['raid_pair'] if side.get('raid_pair') else [side]
                for unit in units:
                    if unit['existing_competition_id']:
                        created.append((unit, unit['existing_competition_id']))
                        continue
                    this_kickoff_status = None if side.get('raid_pair') else kickoff_status
                    comp_id = await _create_and_persist(
                        unit['title'], unit['metric'], side['nominator_user_id'], this_kickoff_status
                    )
                    created.append((unit, comp_id))
        except Exception as exc:
            if len(sides) > 1:
                mod_channel_id = checks.moderator_channel_id()
                mod_channel = interaction.client.get_channel(mod_channel_id)
                if created:
                    done = ', '.join(f"{label['metric_display']} (id {cid})" for label, cid in created)
                    note = (
                        f"{done} created on WOM, but the rest of this pairing failed: {exc}\n"
                        'This will **not** be announced or tracked as OTW — manual '
                        'cleanup on WOM is up to you if you want it removed.'
                    )
                else:
                    note = f'Nothing was created before this pairing failed: {exc}'
                if mod_channel:
                    await mod_channel.send(f'**OTW pairing failed.**\n{note}')
                await interaction.followup.send(
                    'Pairing failed — see the mod channel for details.', ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f'Failed to create the competition on WOM: {exc}\n'
                    'Nothing was created — rerun `/competition create` to retry.',
                    ephemeral=True,
                )
            return

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)

        if len(sides) > 1:
            kickoff_text = announcements.build_kickoff_post(
                payload['starts_at'], payload['ends_at'], sides[0], sides[1]
            )
            draft = (
                '**[DRAFT] Kickoff Announcement — Pending Mod Approval**\n\n'
                f'{kickoff_text}\n\n'
                '-# Click **Approve & Post** to publish to the announcements channel.'
            )
            approval_view = KickoffApprovalView()
        else:
            comp_type = types.TYPES[payload['comp_type_key']]
            kickoff_text = announcements.build_solo_kickoff_post(
                comp_type, payload['starts_at'], payload['ends_at'], sides[0]
            )
            draft = (
                '**[DRAFT] Kickoff Announcement — Pending Mod Approval**\n\n'
                f'{kickoff_text}\n\n'
                '-# Click **Approve & Post** to publish to the announcements channel.'
            )
            approval_view = SoloKickoffApprovalView(created[0][1])

        mod_channel_id = checks.moderator_channel_id()
        mod_channel = interaction.client.get_channel(mod_channel_id)
        if mod_channel is None:
            await interaction.followup.send(
                f'Moderator channel {mod_channel_id} not found — check MODERATOR_CHANNEL. '
                'The competition(s) were created on WOM; the kickoff post still needs to be sent.',
                ephemeral=True,
            )
            return
        await mod_channel.send(draft, view=approval_view)

        await interaction.followup.send(
            'Competition(s) created on WOM. Kickoff post drafted for approval.',
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
        'cycle_id': int or None,
        'comp_type_key': str,  # only present for a single-side (solo) payload
        'sides': [
            {'metric': slug, 'metric_display': str, 'title': str,
             'nominator_user_id': int or None, 'nominator_text': str,
             'existing_competition_id': int or None, 'existing_verification_code': str or None,
             'raid_pair': [{'metric', 'metric_display', 'title',
                            'existing_competition_id', 'existing_verification_code'}, ...] or None},
            ...  # one dict for solo, two (botw, sotw) for a pair
        ],
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

        by_type, fetch_errors = await cycle_lookup.get_competitions_by_type(cycle['id'])
        if fetch_errors:
            row, exc = fetch_errors[0]
            await interaction.followup.send(f'WOM API error fetching competition {row["competition_id"]}: {exc}')
            return

        if 'botw' not in by_type or 'sotw' not in by_type:
            await interaction.followup.send('Competition data is incomplete in the DB. Cannot approve.')
            return

        sotw_row, sotw_detail = by_type['sotw'][0]
        sotw_pick = {
            'title': sotw_detail['title'],
            'metric_display': metrics.display_name('sotw', sotw_detail['metric']),
            'nominator_text': _nominator_mention(sotw_row['nominator_user_id']),
        }

        botw_rows = by_type['botw']
        if len(botw_rows) == 1:
            botw_row, botw_detail = botw_rows[0]
            botw_pick = {
                'title': botw_detail['title'],
                'metric_display': metrics.display_name('botw', botw_detail['metric']),
                'nominator_text': _nominator_mention(botw_row['nominator_user_id']),
            }
        elif len(botw_rows) == 2:
            metrics_seen = {d['metric'] for _, d in botw_rows}
            pair = raid_pairs.pair_for_metric(next(iter(metrics_seen)))
            if pair is None or metrics_seen != {pair.base_metric, pair.hard_metric}:
                await interaction.followup.send(
                    "This cycle has two BOTW competitions but they don't form a recognized raid pair. Cannot approve."
                )
                return
            by_metric = {d['metric']: (r, d) for r, d in botw_rows}
            base_row, base_detail = by_metric[pair.base_metric]
            hard_row, hard_detail = by_metric[pair.hard_metric]
            botw_pick = {
                'title': f'{base_detail["title"]}\n{hard_detail["title"]}',
                'metric_display': pair.display_name,
                'nominator_text': _nominator_mention(base_row['nominator_user_id']),
            }
        else:
            await interaction.followup.send(f'Unexpected number of BOTW competitions ({len(botw_rows)}) for this cycle. Cannot approve.')
            return

        text = announcements.build_kickoff_post(
            cycle['starts_at'], cycle['ends_at'], botw_pick, sotw_pick
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


# -----------------------------------------------------------------------------
# Solo (standalone) competition kickoff announcement approval gate
# -----------------------------------------------------------------------------

class ApproveSoloKickoffButton(discord.ui.Button):
    def __init__(self, competition_id):
        super().__init__(
            label='Approve & Post',
            style=discord.ButtonStyle.green,
            custom_id=f'comp_approve_solo_kickoff:{competition_id}',
        )
        self.competition_id = competition_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

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

        row = await asyncio.to_thread(comp_db.get_competition_by_id, self.competition_id)
        nominator_user_id = row['nominator_user_id'] if row else None
        side = {
            'title': detail['title'],
            'metric_display': metrics.display_name(comp_type.key, detail['metric']),
            'nominator_text': _nominator_mention(nominator_user_id),
        }
        starts_at = to_local_dt(detail['startsAt'])
        ends_at = to_local_dt(detail['endsAt'])
        text = announcements.build_solo_kickoff_post(comp_type, starts_at, ends_at, side)

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

        await asyncio.to_thread(comp_db.set_kickoff_status, self.competition_id, 'announced')

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        await interaction.followup.send('Kickoff post published.')


class DismissSoloKickoffButton(discord.ui.Button):
    def __init__(self, competition_id):
        super().__init__(
            label='Dismiss',
            style=discord.ButtonStyle.red,
            custom_id=f'comp_dismiss_solo_kickoff:{competition_id}',
        )
        self.competition_id = competition_id

    async def callback(self, interaction: discord.Interaction):
        await asyncio.to_thread(comp_db.set_kickoff_status, self.competition_id, 'announced')

        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message('Dismissed.')


class SoloKickoffApprovalView(discord.ui.View):
    """Persistent approval gate for a standalone (non-OTW) competition's kickoff.

    Keyed by competition_id (unlike KickoffApprovalView, which is keyed by cycle and
    requires both a BOTW and SOTW side) since solo competitions never get a cycle_id.
    The bot must call bot.add_view(SoloKickoffApprovalView(competition_id)) in on_ready
    for every still-drafted solo kickoff to re-register the handler after a restart.
    """

    def __init__(self, competition_id):
        super().__init__(timeout=None)
        self.add_item(ApproveSoloKickoffButton(competition_id))
        self.add_item(DismissSoloKickoffButton(competition_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not checks.moderator_interaction(interaction):
            await interaction.response.send_message(
                'Moderators only, in the mod channel.', ephemeral=True)
            return False
        return True
