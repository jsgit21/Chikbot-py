import asyncio
import datetime
import os

import discord
from discord.ext import commands, tasks

import database.db_methods as db_methods
from shared import tz
from ..identity import db as identity_db
from ..shared import checks
from . import announcements, db as comp_db, event_calendar, metrics, raid_pairs, scheduling, types, winners, wom_api
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
                           existing_rows=None, existing_details=None):
        """Resolve the nominator and assemble one competition's preview payload.

        existing_rows / existing_details: parallel lists of resumed DB row(s)/detail(s)
        if this side was already (partially) created on a prior /competition create-otw
        attempt. A normal side has at most one entry; a raid-pair BOTW side can have 0
        (neither half created yet), 1, or 2. Always empty for the standalone create()
        command, which has no resume concept.
        """
        comp_type = types.TYPES[comp_type_key]
        nominator_id, nominator_alias = await self._resolve_nominator(
            guild, explicit_member, last_cycle, comp_type_key
        )

        pair = raid_pairs.pair_for_metric(metric) if comp_type_key == 'botw' else None

        if pair is None:
            existing_row = existing_rows[0] if existing_rows else None
            existing_detail = existing_details[0] if existing_details else None
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
                'raid_pair': None,
            }

        # Raid-pair side: two WOM-competition creation specs, one per mode, each
        # independently resumable. Title uses comp_type.display_name ('BOTW') rather
        # than title_label ('Boss of the Week') to fit WOM's title length constraint --
        # see raid_pairs.py's module docstring and this plan's Context section.
        existing_by_metric = {d['metric']: (r, d) for r, d in zip(existing_rows or [], existing_details or [])}

        def _half(half_metric, half_label):
            existing_row, existing_detail = existing_by_metric.get(half_metric, (None, None))
            title = existing_detail['title'] if existing_detail else (
                f"{half_label} - {comp_type.display_name} [{nominator_alias}'s pick]"
            )
            return {
                'metric': half_metric, 'metric_display': half_label, 'title': title,
                'existing_competition_id': existing_row['competition_id'] if existing_row else None,
                'existing_verification_code': existing_row['verification_code'] if existing_row else None,
            }

        base_half = _half(pair.base_metric, pair.base_label)
        hard_half = _half(pair.hard_metric, pair.hard_label)

        return {
            'metric': metric, 'metric_display': pair.display_name,
            'title': f'{base_half["title"]}\n{hard_half["title"]}',
            'nominator_user_id': existing_rows[0]['nominator_user_id'] if existing_rows else nominator_id,
            'nominator_text': f'<@{nominator_id}>' if nominator_id else nominator_alias,
            'existing_competition_id': None, 'existing_verification_code': None,
            'raid_pair': [base_half, hard_half],
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
                    existing_by_type.setdefault(comp_type.key, []).append((row, detail))

        existing_botw = existing_by_type.get('botw', [])
        existing_sotw = existing_by_type.get('sotw', [])

        botw_side = await self._build_side(
            ctx.guild, 'botw', botw_metric, botw_nominator, last_cycle,
            existing_rows=[r for r, _ in existing_botw], existing_details=[d for _, d in existing_botw],
        )
        sotw_side = await self._build_side(
            ctx.guild, 'sotw', sotw_metric, sotw_nominator, last_cycle,
            existing_rows=[r for r, _ in existing_sotw], existing_details=[d for _, d in existing_sotw],
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
            botw_total = 2 if raid_pairs.pair_for_metric(botw_metric) else 1
            done = []
            if existing_botw:
                done.append(
                    'BOTW' if len(existing_botw) >= botw_total
                    else f'BOTW ({len(existing_botw)}/{botw_total} halves)'
                )
            if existing_sotw:
                done.append('SOTW')
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
                         choices=[
                             discord.OptionChoice(name=t.display_name, value=key)
                             for key, t in types.TYPES.items() if t.creatable
                         ],
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

        if comp_type == 'botw' and raid_pairs.pair_for_metric(metric) is not None:
            await ctx.respond(
                f'`{metrics.display_name("botw", metric)}` needs two linked competitions (one per mode) — '
                'use `/competition create-otw` instead of the standalone `/competition create` for this pick.',
                ephemeral=True,
            )
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
        next SOTW target; SOTW winner picks the next BOTW target). If last
        cycle's source side was a raid pair, resolves the combined/max-of
        winner across both halves rather than an arbitrary one.
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

        matches = []
        for row in comps:
            try:
                detail = await asyncio.to_thread(wom_api.get_competition, row['competition_id'])
            except Exception:
                continue
            inferred = types.infer_type_from_title(detail.get('title', ''))
            if inferred and inferred.key == source_type:
                matches.append(detail)

        winner = None
        if len(matches) == 2:
            pair = raid_pairs.pair_for_metric(matches[0]['metric'])
            if pair is not None:
                by_metric = {d['metric']: d for d in matches}
                if pair.base_metric in by_metric and pair.hard_metric in by_metric:
                    winner = winners.resolve_paired_winner(
                        pair, by_metric[pair.base_metric], by_metric[pair.hard_metric]
                    )
        if winner is None and matches:
            winner = winners.resolve_winner(matches[0])

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
        handled_pair_ids = set()

        try:
            competitions = await asyncio.to_thread(wom_api.list_group_competitions)
        except Exception as exc:
            await mod_channel.send(f'Winner detection: WOM API error fetching competitions: {exc}')
            competitions = []

        unprocessed = await asyncio.to_thread(comp_db.get_unprocessed_competitions)
        for row in unprocessed:
            if row['competition_id'] in handled_pair_ids:
                continue

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
                await self._notify_unhandled_competition(
                    mod_channel, row['competition_id'], detail.get('title'),
                    "doesn't match a known competition type."
                )
                continue

            pair = raid_pairs.pair_for_metric(detail.get('metric'))
            if pair is not None:
                if await self._handle_raid_pair_candidate(
                    detail, True, comp_type, pair, competitions, handled_pair_ids, mod_channel
                ):
                    processed_any = True
                continue

            await self._handle_competition_ended(detail, detail, row, comp_type, mod_channel)
            processed_any = True

        for summary in wom_api.find_ended_competitions(competitions):
            if summary['id'] in handled_pair_ids:
                continue

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
                await self._notify_unhandled_competition(
                    mod_channel, summary['id'], detail.get('title'),
                    "doesn't match a known competition type."
                )
                continue

            if not comp_type.results_enabled:
                await self._notify_unhandled_competition(
                    mod_channel, summary['id'], detail.get('title'),
                    f"matched {comp_type.display_name}, which isn't wired up for automated results yet."
                )
                continue

            pair = raid_pairs.pair_for_metric(detail.get('metric'))
            if pair is not None:
                if await self._handle_raid_pair_candidate(
                    detail, False, comp_type, pair, competitions, handled_pair_ids, mod_channel
                ):
                    processed_any = True
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

        await self._check_standalone_cadence_nudges(mod_channel, competitions)

    async def _handle_no_active_cycle(self, mod_channel):
        """Nudge mods on a Monday with nothing ended and nothing queued.

        On-cadence (within the normal one-break-week gap) gets a plain prompt
        to run /competition create-otw; anything longer is treated as a deliberate
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
                "Run `/competition create-otw` to keep the cadence going."
            )
        else:
            await mod_channel.send(
                f"-# BOTW/SOTW has been on break for {weeks_since} weeks. Reply with picks "
                "and I'll queue up the next cycle whenever you're ready "
                "(`/competition create-otw` targets the next available Saturday; "
                "raise `weeks_out` to push it further)."
            )

    async def _notify_unhandled_competition(self, mod_channel, comp_id, title, reason):
        """Fail loudly in the mod channel for an ended competition winner detection
        won't touch, so it doesn't just silently disappear from view.
        """
        await mod_channel.send(
            f'Winner detection: competition {comp_id} ("{title}") {reason} '
            "It might be a good idea to post the results for that event if they "
            "haven't been made public yet, or open a chikbot-py repo issue to "
            "integrate that event type's automation."
        )

    async def _check_standalone_cadence_nudges(self, mod_channel, competitions):
        """Nudge mods for any standalone type that's overdue per its own cadence.

        Independent of _handle_no_active_cycle above: OTW tracks "last run" and
        "currently active" via competition_cycle, but standalone types (lucky_learner,
        bingo, ...) never get a cycle_id, so their history has to come from WOM's
        competition list directly instead. Reuses the same list _run_winner_detection's
        pass 2 already fetched this run.

        A type with no WOM-visible history yet (nothing tagged, or the last one predates
        this feature) falls back to its nudge_seed_last_ended, if one is configured, so
        the cadence doesn't need a live-detected competition to start counting from.
        """
        now = datetime.datetime.utcnow()

        for comp_type in types.TYPES.values():
            if comp_type.nudge_cadence_weeks is None:
                continue

            matches = []
            for c in competitions:
                inferred = types.infer_type_from_title(c.get('title', ''))
                if inferred and inferred.key == comp_type.key:
                    matches.append(c)

            if any(c.get('endsAt') and _parse_iso(c['endsAt']) >= now for c in matches):
                continue  # one's currently running or scheduled

            ended = [c for c in matches if c.get('endsAt') and _parse_iso(c['endsAt']) < now]
            if ended:
                last_ends_at = max(_parse_iso(c['endsAt']) for c in ended)
            elif comp_type.nudge_seed_last_ended is not None:
                last_ends_at = comp_type.nudge_seed_last_ended
            else:
                continue  # never run yet -- nothing to measure a gap against

            weeks_since = scheduling.weeks_since_last_cycle(last_ends_at, now.date())
            if weeks_since >= comp_type.nudge_cadence_weeks:
                await mod_channel.send(
                    f"-# It's been {weeks_since} weeks since the last {comp_type.display_name}. "
                    'Might be time to organize the next one.'
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

    async def _handle_raid_pair_candidate(self, detail, has_db_row, comp_type, pair,
                                           competitions, handled_pair_ids, mod_channel):
        """Handle one ended half of a split-raid BOTW pick: find its sibling half
        and, if found, draft ONE combined result instead of processing this half
        alone. Returns True if a combined draft was posted this call.

        has_db_row: True from pass 1 (a DB row already tracks this half), False
        from pass 2 (found live on WOM, no DB row). Only a pass-1 half escalates
        to a fail-loud notice on a stale orphan -- a pass-2 half with no DB row
        simply ages out of find_ended_competitions' own lookback window, same as
        any other undiscovered competition today.
        """
        this_id = detail['id']
        if this_id in handled_pair_ids:
            return False

        sibling_detail = await raid_pairs.find_sibling(detail, competitions)

        if sibling_detail is None:
            if has_db_row and (datetime.datetime.utcnow() - _parse_iso(detail['endsAt'])).days >= raid_pairs.ORPHAN_ESCALATION_DAYS:
                sibling_metric = raid_pairs.partner_metric(detail['metric'])
                await self._notify_unhandled_competition(
                    mod_channel, this_id, detail.get('title'),
                    f'is one half of a {pair.display_name} raid pair, but no sibling '
                    f'({raid_pairs.label_for_metric(sibling_metric)}) has been found on WOM in the '
                    f'{raid_pairs.ORPHAN_ESCALATION_DAYS} days since it ended.'
                )
            return False

        sibling_id = sibling_detail['id']
        handled_pair_ids.add(this_id)
        handled_pair_ids.add(sibling_id)

        base_detail, hard_detail = (
            (detail, sibling_detail) if detail['metric'] == pair.base_metric else (sibling_detail, detail)
        )

        conflicts = []
        try:
            winner = winners.resolve_paired_winner(pair, base_detail, hard_detail)
        except Exception as exc:
            winner = None
            conflicts.append(
                f'Error resolving the combined {pair.display_name} winner: {exc}. '
                'Event-calendar fallback is not available for raid pairs — verify manually before approving.'
            )

        if winner is None and not conflicts:
            conflicts.append(f'No {pair.display_name} participants with recorded progress in either half.')
        elif winner and winner['discord_user_id'] is None:
            conflicts.append(
                f'{pair.display_name} winner `{winner["rsn"]}` has no Discord link — '
                'have a mod run `/wom link`, or ask the winner to run `/wom claim` themselves, '
                'before approving.'
            )

        base_row = await asyncio.to_thread(comp_db.get_competition_by_id, base_detail['id'])
        hard_row = await asyncio.to_thread(comp_db.get_competition_by_id, hard_detail['id'])
        cycle_id = (base_row['cycle_id'] if base_row else None) or (hard_row['cycle_id'] if hard_row else None)

        await asyncio.to_thread(comp_db.ensure_competition_row, base_detail['id'], cycle_id)
        await asyncio.to_thread(comp_db.ensure_competition_row, hard_detail['id'], cycle_id)
        await asyncio.to_thread(comp_db.set_results_status, base_detail['id'], 'drafted')
        await asyncio.to_thread(comp_db.set_results_status, hard_detail['id'], 'drafted')

        draft = _build_raid_pair_draft(comp_type, pair, winner, conflicts, base_detail['id'], hard_detail['id'])
        await mod_channel.send(draft, view=ResultsApprovalView(base_detail['id']))

        await self._maybe_mark_cycle_ended(cycle_id)
        return True

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


def _build_raid_pair_draft(comp_type, pair, winner, conflicts, base_id, hard_id):
    lines = [
        f'**[DRAFT] {comp_type.display_name} Results — {pair.display_name} — Pending Mod Approval**',
        f'-# Competitions {base_id} ({pair.base_label}) + {hard_id} ({pair.hard_label})',
        '',
        announcements.build_raid_pair_result_post(comp_type, pair, winner),
    ]
    if conflicts:
        lines += ['', '**Issues to resolve before approving:**']
        lines += [f'- {c}' for c in conflicts]
    lines += ['', '-# Click **Approve & Post** to publish to the announcements channel and assign the winner role.']
    return '\n'.join(lines)


def setup(bot):
    bot.add_cog(Competitions(bot))
