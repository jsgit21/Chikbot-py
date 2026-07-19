import asyncio
import datetime
import os

import discord
from discord.ext import commands, tasks

import database.db_methods as db_methods
from shared import tz
from ..identity import db as identity_db
from ..shared import checks
from . import announcements, db as comp_db, event_calendar, metrics, scheduling, types, winners, wom_api
from .views import ConfirmCreateView, KickoffApprovalView, ResultsApprovalView, SoloKickoffApprovalView


class Competitions(commands.Cog):

    competition = discord.SlashCommandGroup('competition', 'BOTW/SOTW competition management')

    def __init__(self, bot):
        self.bot = bot
        self.MOD_CHANNEL_ID = checks.moderator_channel_id()
        self.winner_detection.start()
        self.refresh_metrics.start()

    @property
    def mod_channel(self):
        return self.bot.get_channel(self.MOD_CHANNEL_ID)

    # -------------------------------------------------------------------------
    # Persistent view registration
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        drafted = await asyncio.to_thread(comp_db.get_drafted_competitions)
        for row in drafted:
            self.bot.add_view(ResultsApprovalView(row['competition_id']))
        self.bot.add_view(KickoffApprovalView())

        awaiting_kickoff = await asyncio.to_thread(comp_db.get_competitions_awaiting_kickoff)
        for row in awaiting_kickoff:
            self.bot.add_view(SoloKickoffApprovalView(row['competition_id']))

    # -------------------------------------------------------------------------
    # Monday detection loop
    # -------------------------------------------------------------------------

    # tzinfo must stay explicit: discord.py's tasks.loop forces UTC on a naive
    # time= regardless of the host OS's timezone, so dropping this would silently
    # shift the loop off its intended ET wall-clock time.
    @tasks.loop(time=datetime.time(hour=12, minute=0, tzinfo=tz.ET))
    async def winner_detection(self):
        if datetime.datetime.now().weekday() != 0:
            return
        await self._run_winner_detection()

    @winner_detection.before_loop
    async def before_winner_detection(self):
        await self.bot.wait_until_ready()

    # -------------------------------------------------------------------------
    # Live metric list refresh
    # -------------------------------------------------------------------------

    # tzinfo must stay explicit: discord.py's tasks.loop forces UTC on a naive
    # time= regardless of the host OS's timezone, so dropping this would silently
    # shift the loop off its intended ET wall-clock time.
    @tasks.loop(time=datetime.time(hour=13, minute=30, tzinfo=tz.ET))
    async def refresh_metrics(self):
        rsn = await asyncio.to_thread(comp_db.get_any_group_rsn)
        if not rsn:
            return
        try:
            await asyncio.to_thread(metrics.refresh_live_metrics, rsn)
        except Exception as exc:
            await self.mod_channel.send(
                f'Metric list refresh failed, keeping the last known list: {exc}'
            )

    @refresh_metrics.before_loop
    async def before_refresh_metrics(self):
        await self.bot.wait_until_ready()

    # -------------------------------------------------------------------------
    # /competition create-otw
    # -------------------------------------------------------------------------

    async def _build_side(self, guild, comp_type_key, metric, explicit_member, last_cycle,
                           existing_row=None, existing_detail=None):
        """Resolve the nominator and assemble one competition's preview payload.

        existing_row / existing_detail: the resumed DB row and live WOM detail if this
        side of a paired cycle was already created on a prior /competition create-otw
        attempt. Always None for the standalone create() command, which has no resume
        concept (solo competitions never get a cycle_id).
        """
        comp_type = types.TYPES[comp_type_key]
        nominator_id, nominator_alias = await self._resolve_nominator(
            guild, explicit_member, last_cycle, comp_type_key
        )
        display = metrics.display_name(comp_type_key, metric)
        title = existing_detail['title'] if existing_detail else (
            f"{display} - {comp_type.title_label} [{nominator_alias}'s pick]"
        )
        return {
            'metric': existing_detail['metric'] if existing_detail else metric,
            'metric_display': display, 'title': title,
            'nominator_user_id': existing_row['nominator_user_id'] if existing_row else nominator_id,
            'nominator_text': f'<@{nominator_id}>' if nominator_id else nominator_alias,
            'existing_competition_id': existing_row['competition_id'] if existing_row else None,
            'existing_verification_code': existing_row['verification_code'] if existing_row else None,
        }

    @competition.command(name='create-otw', description='Create the next BOTW/SOTW competitions and draft a kickoff post')
    @commands.check(checks.moderator_command)
    async def create_otw(self, ctx,
                     botw_metric: discord.Option(
                         str, 'Boss metric for BOTW',
                         autocomplete=metrics.autocomplete_botw_metric, required=True),
                     sotw_metric: discord.Option(
                         str, 'Skill metric for SOTW',
                         autocomplete=metrics.autocomplete_sotw_metric, required=True),
                     weeks_out: discord.Option(
                         int, 'Weeks beyond the next available Saturday (0 = next available)',
                         required=False) = 0,
                     botw_nominator: discord.Option(
                         discord.Member, "Who nominated the BOTW boss (default: last cycle's SOTW winner)",
                         required=False) = None,
                     sotw_nominator: discord.Option(
                         discord.Member, "Who nominated the SOTW skill (default: last cycle's BOTW winner)",
                         required=False) = None):
        await ctx.defer()

        if botw_metric not in metrics.all_botw_metrics():
            await ctx.respond(f'`{botw_metric}` is not a valid BOTW metric.', ephemeral=True)
            return
        if sotw_metric not in metrics.all_sotw_metrics():
            await ctx.respond(f'`{sotw_metric}` is not a valid SOTW metric.', ephemeral=True)
            return

        last_cycle = await asyncio.to_thread(comp_db.get_last_cycle)
        after = last_cycle['ends_at'] if last_cycle else datetime.datetime.now().date()
        starts_at, ends_at = scheduling.next_cycle_window(after, weeks_out=weeks_out)

        existing_cycle = await asyncio.to_thread(
            comp_db.get_planned_cycle_for_window, starts_at, ends_at
        )
        existing_by_type = {}
        if existing_cycle:
            existing_comps = await asyncio.to_thread(
                comp_db.get_competitions_for_cycle, existing_cycle['id']
            )
            for row in existing_comps:
                try:
                    detail = await asyncio.to_thread(wom_api.get_competition, row['competition_id'])
                except Exception:
                    continue
                comp_type = types.infer_type_from_title(detail.get('title', ''))
                if comp_type:
                    existing_by_type[comp_type.key] = (row, detail)

        existing_botw, existing_botw_detail = existing_by_type.get('botw', (None, None))
        existing_sotw, existing_sotw_detail = existing_by_type.get('sotw', (None, None))

        botw_side = await self._build_side(
            ctx.guild, 'botw', botw_metric, botw_nominator, last_cycle, existing_botw, existing_botw_detail
        )
        sotw_side = await self._build_side(
            ctx.guild, 'sotw', sotw_metric, sotw_nominator, last_cycle, existing_sotw, existing_sotw_detail
        )

        payload = {
            'starts_at': starts_at,
            'ends_at': ends_at,
            'cycle_id': existing_cycle['id'] if existing_cycle else None,
            'sides': [botw_side, sotw_side],
        }

        start_et = starts_at
        end_et = ends_at
        resuming_note = ''
        if existing_cycle:
            done = [t for t, c in (('BOTW', existing_botw), ('SOTW', existing_sotw)) if c]
            resuming_note = (
                f'\n-# Resuming an existing cycle for this window — {", ".join(done)} '
                'already created on WOM and will not be duplicated.\n'
            )
        preview = (
            '**Preview — /competition create**\n\n'
            f'**BOTW** — {botw_side["title"]}\n'
            f'**SOTW** — {sotw_side["title"]}\n\n'
            f'Runs **{start_et.strftime("%a %Y-%m-%d %H:%M")}** → '
            f'**{end_et.strftime("%a %Y-%m-%d %H:%M")} ET**\n'
            f'{resuming_note}\n'
            '-# Click **Confirm & Create** to create both competitions on WOM.'
        )
        await ctx.respond(preview, view=ConfirmCreateView(payload))

    # -------------------------------------------------------------------------
    # /competition create
    # -------------------------------------------------------------------------

    @competition.command(name='create', description='Create a single standalone competition and draft a kickoff post')
    @commands.check(checks.moderator_command)
    async def create(self, ctx,
                     comp_type: discord.Option(
                         str, 'Competition type',
                         choices=[discord.OptionChoice(name=t.display_name, value=key) for key, t in types.TYPES.items()],
                         required=True),
                     metric: discord.Option(
                         str, 'Metric for the competition',
                         autocomplete=metrics.autocomplete_metric, required=True),
                     weeks_out: discord.Option(
                         int, 'Weeks beyond the next available Saturday (0 = next available)',
                         required=False) = 0,
                     nominator: discord.Option(
                         discord.Member, 'Who nominated this competition (default: the group)',
                         required=False) = None):
        await ctx.defer()

        if metric not in metrics.all_metrics_for(comp_type):
            await ctx.respond(f'`{metric}` is not a valid metric for {comp_type}.', ephemeral=True)
            return

        last_cycle = await asyncio.to_thread(comp_db.get_last_cycle)
        after = last_cycle['ends_at'] if last_cycle else datetime.datetime.now().date()
        starts_at, ends_at = scheduling.next_cycle_window(after, weeks_out=weeks_out)

        side = await self._build_side(ctx.guild, comp_type, metric, nominator, last_cycle)

        payload = {
            'starts_at': starts_at,
            'ends_at': ends_at,
            'cycle_id': None,
            'comp_type_key': comp_type,
            'sides': [side],
        }

        preview = (
            '**Preview — /competition create**\n\n'
            f'**{types.TYPES[comp_type].display_name}** — {side["title"]}\n\n'
            f'Runs **{starts_at.strftime("%a %Y-%m-%d %H:%M")}** → '
            f'**{ends_at.strftime("%a %Y-%m-%d %H:%M")} ET**\n\n'
            '-# Click **Confirm & Create** to create this competition on WOM.'
        )
        await ctx.respond(preview, view=ConfirmCreateView(payload))

    async def _resolve_nominator(self, guild, explicit_member, last_cycle, comp_type):
        """Return (nominator_user_id, nominator_alias) for a BOTW/SOTW pick.

        An explicit member selection wins; otherwise defaults to the
        cross-assigned winner from the last cycle (BOTW winner picks the
        next SOTW target; SOTW winner picks the next BOTW target).
        """
        if explicit_member:
            await asyncio.to_thread(db_methods.register_user, explicit_member)
            alias = await asyncio.to_thread(identity_db.get_alias, explicit_member.id)
            return explicit_member.id, (alias or explicit_member.display_name)

        if not last_cycle:
            return None, 'the group'

        source_type_obj = types.nominator_source_for(comp_type)
        if not source_type_obj:
            return None, 'the group'
        source_type = source_type_obj.key
        comps = await asyncio.to_thread(comp_db.get_competitions_for_cycle, last_cycle['id'])

        winner = None
        for row in comps:
            try:
                detail = await asyncio.to_thread(wom_api.get_competition, row['competition_id'])
            except Exception:
                continue
            inferred = types.infer_type_from_title(detail.get('title', ''))
            if inferred and inferred.key == source_type:
                winner = winners.resolve_winner(detail)
                break

        if not winner or not winner['discord_user_id']:
            return None, 'the group'

        user_id = winner['discord_user_id']
        alias = winner['alias']
        if not alias:
            member = guild.get_member(user_id)
            alias = member.display_name if member else 'the group'
        return user_id, alias

    # -------------------------------------------------------------------------
    # Debug command
    # -------------------------------------------------------------------------

    @competition.command(description='Manually trigger the Monday winner-detection job')
    @commands.check(checks.moderator_command)
    async def debug_run(self, ctx):
        await ctx.respond('Running winner detection...', ephemeral=True)
        await self._run_winner_detection()

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.respond(
                'This command is for moderators in the mod channel only.',
                ephemeral=True,
            )
        else:
            raise error

    # -------------------------------------------------------------------------
    # Core detection logic
    # -------------------------------------------------------------------------

    async def _run_winner_detection(self):
        """Two passes: our own tracked backlog (unbounded), then a bounded
        lookback scan for competitions never created via /competition create.
        """
        mod_channel = self.mod_channel
        processed_any = False

        unprocessed = await asyncio.to_thread(comp_db.get_unprocessed_competitions)
        for row in unprocessed:
            try:
                detail = await asyncio.to_thread(wom_api.get_competition, row['competition_id'])
            except Exception as exc:
                await mod_channel.send(
                    f'Winner detection: WOM API error fetching competition {row["competition_id"]}: {exc}'
                )
                continue

            if _parse_iso(detail['endsAt']) >= datetime.datetime.utcnow():
                continue

            comp_type = types.infer_type_from_title(detail.get('title', ''))
            if comp_type is None:
                await mod_channel.send(
                    f'Winner detection: competition {row["competition_id"]} '
                    f'("{detail.get("title")}") doesn\'t match a known competition type.'
                )
                continue

            await self._handle_competition_ended(detail, detail, row, comp_type, mod_channel)
            processed_any = True

        try:
            competitions = await asyncio.to_thread(wom_api.list_group_competitions)
        except Exception as exc:
            await mod_channel.send(f'Winner detection: WOM API error fetching competitions: {exc}')
            competitions = []

        for summary in wom_api.find_ended_competitions(competitions):
            existing_row = await asyncio.to_thread(comp_db.get_competition_by_id, summary['id'])
            if existing_row:
                continue  # already covered by pass 1, or already resolved

            try:
                detail = await asyncio.to_thread(wom_api.get_competition, summary['id'])
            except Exception as exc:
                await mod_channel.send(
                    f'Winner detection: WOM API error fetching competition {summary["id"]}: {exc}'
                )
                continue

            comp_type = types.infer_type_from_title(detail.get('title', ''))
            if comp_type is None:
                await mod_channel.send(
                    f'Winner detection: competition {summary["id"]} '
                    f'("{detail.get("title")}") doesn\'t match a known competition type.'
                )
                continue

            await self._handle_competition_ended(summary, detail, None, comp_type, mod_channel)
            processed_any = True

        if not processed_any:
            await self._handle_no_active_cycle(mod_channel)
        else:
            await mod_channel.send(
                '-# Reminder: collect picks from both winners before next Sunday '
                '(BOTW winner picks next SOTW; SOTW winner picks next BOTW).'
            )

    async def _handle_no_active_cycle(self, mod_channel):
        """Nudge mods on a Monday with nothing ended and nothing queued.

        On-cadence (within the normal one-break-week gap) gets a plain prompt
        to run /competition create; anything longer is treated as a deliberate
        pause and gets a softer "been X weeks" reminder instead.
        """
        planned = await asyncio.to_thread(comp_db.get_planned_cycles)
        if planned:
            return

        active = await asyncio.to_thread(comp_db.get_active_cycles)
        if active:
            return

        last_cycle = await asyncio.to_thread(comp_db.get_last_cycle)
        if not last_cycle:
            return

        weeks_since = scheduling.weeks_since_last_cycle(
            last_cycle['ends_at'], datetime.datetime.now().date()
        )

        if weeks_since <= 2:
            await mod_channel.send(
                "-# It's Monday and no BOTW/SOTW competitions are running or queued. "
                "Run `/competition create` to keep the cadence going."
            )
        else:
            await mod_channel.send(
                f"-# BOTW/SOTW has been on break for {weeks_since} weeks. Reply with picks "
                "and I'll queue up the next cycle whenever you're ready "
                "(`/competition create` targets the next available Saturday; "
                "raise `weeks_out` to push it further)."
            )

    async def _handle_competition_ended(self, summary, detail, existing_row, comp_type, mod_channel):
        """Resolve, persist, and draft results for a single ended competition.

        Nothing WOM-derivable gets written to the DB here — winner and type
        are re-derived live again at Approve/Dismiss click time.
        """
        conflicts = []
        try:
            winner = winners.resolve_winner(detail)
        except Exception as exc:
            await mod_channel.send(
                f'Error resolving the {comp_type.display_name} winner for competition '
                f'{summary["id"]}: {exc}\nAttempting event-calendar fallback...'
            )
            winner = None
            try:
                parsed = await self._event_calendar_fallback(summary['id'])
            except Exception as fallback_exc:
                parsed = None
                await mod_channel.send(f'Event-calendar fallback also failed: {fallback_exc}')
            if parsed:
                winner = winners.resolve_winner_from_fallback(parsed, summary['id'])
                conflicts.append(
                    'Winner sourced from event-calendar fallback (WOM API was unavailable) — '
                    'verify before approving.'
                )

        if winner is None:
            conflicts.append(f'No {comp_type.display_name} participants with recorded progress.')
        elif winner['discord_user_id'] is None:
            conflicts.append(
                f'{comp_type.display_name} winner `{winner["rsn"]}` has no Discord link — '
                'have a mod run `/wom link`, or ask the winner to run `/wom claim` themselves, '
                'before approving.'
            )

        cycle_id = existing_row['cycle_id'] if existing_row else None
        await asyncio.to_thread(comp_db.ensure_competition_row, summary['id'], cycle_id)
        await asyncio.to_thread(comp_db.set_results_status, summary['id'], 'drafted')

        draft = _build_draft(comp_type, winner, conflicts)
        await mod_channel.send(draft, view=ResultsApprovalView(summary['id']))

        await self._maybe_mark_cycle_ended(cycle_id)

    async def _event_calendar_fallback(self, competition_id):
        """Read the event-calendar channel and match a message to this competition id."""
        ec_id = os.getenv('EVENT_CALENDAR_CHANNEL')
        wom_bot_id_str = os.getenv('WOM_DISCORD_BOT_ID')
        if not ec_id or not wom_bot_id_str:
            return None

        ec_channel = self.bot.get_channel(int(ec_id))
        if not ec_channel:
            return None

        wom_bot_id = int(wom_bot_id_str)
        messages = await ec_channel.history(limit=50).flatten()
        wom_messages = [m for m in messages if m.author.id == wom_bot_id]

        for msg in wom_messages:
            parsed = event_calendar.parse_result_message(msg)
            if parsed['competition_id'] == competition_id:
                return parsed

        return None

    async def _maybe_mark_cycle_ended(self, cycle_id):
        """Flip a cycle to 'ended' once every competition sharing it is resolved."""
        if not cycle_id:
            return
        comps = await asyncio.to_thread(comp_db.get_competitions_for_cycle, cycle_id)
        if comps and all(c['results_status'] != 'pending' for c in comps):
            await asyncio.to_thread(comp_db.set_cycle_status, cycle_id, 'ended')


# -------------------------------------------------------------------------
# Module-level helpers
# -------------------------------------------------------------------------

def _parse_iso(iso_str):
    """Parse an ISO-8601 UTC string from the WOM API into a naive UTC datetime."""
    return datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00')).replace(tzinfo=None)


def _build_draft(comp_type, winner, conflicts):
    lines = [
        f'**[DRAFT] {comp_type.display_name} Results — Pending Mod Approval**',
        '',
        announcements.build_result_post(comp_type, winner),
    ]
    if conflicts:
        lines += ['', '**Issues to resolve before approving:**']
        lines += [f'- {c}' for c in conflicts]
    lines += [
        '',
        '-# Click **Approve & Post** to publish to the announcements channel and assign the winner role.',
    ]
    return '\n'.join(lines)


def setup(bot):
    bot.add_cog(Competitions(bot))
