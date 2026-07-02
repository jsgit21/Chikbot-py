import asyncio
import datetime
import os

import discord
from discord.ext import commands, tasks

from ..shared import checks, tz
from . import announcements, db as comp_db, event_calendar, winners, wom_api
from .views import ResultsApprovalView


class Competitions(commands.Cog):

    competition = discord.SlashCommandGroup('competition', 'BOTW/SOTW competition management')

    def __init__(self, bot):
        self.bot = bot
        self.MOD_CHANNEL_ID = int(os.getenv('MODERATOR_CHANNEL'))
        self.winner_detection.start()

    @property
    def mod_channel(self):
        return self.bot.get_channel(self.MOD_CHANNEL_ID)

    # -------------------------------------------------------------------------
    # Persistent view registration
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(ResultsApprovalView())

    # -------------------------------------------------------------------------
    # Monday detection loop
    # -------------------------------------------------------------------------

    @tasks.loop(time=datetime.time(hour=12, minute=0, tzinfo=tz.ET))
    async def winner_detection(self):
        if datetime.datetime.now(tz.ET).weekday() != 0:
            return
        await self._run_winner_detection()

    @winner_detection.before_loop
    async def before_winner_detection(self):
        await self.bot.wait_until_ready()

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
        mod_channel = self.mod_channel

        try:
            competitions = await asyncio.to_thread(wom_api.list_group_competitions)
        except Exception as exc:
            await mod_channel.send(f'Winner detection: WOM API error fetching competitions: {exc}')
            return

        botw_summary, sotw_summary = wom_api.find_ended_competition_pair(competitions)
        if not botw_summary or not sotw_summary:
            return

        # Skip if this BOTW competition is already in our DB with results posted.
        existing = await asyncio.to_thread(comp_db.get_competition_by_id, botw_summary['id'])
        if existing and existing['results_posted']:
            return

        botw_winner, sotw_winner, conflicts = await self._resolve_winners(
            botw_summary, sotw_summary, mod_channel
        )
        if botw_winner is None and sotw_winner is None and not conflicts:
            return  # _resolve_winners already posted an error

        cycle_id = await self._ensure_cycle(botw_summary, existing)

        await asyncio.to_thread(
            comp_db.upsert_competition,
            botw_summary['id'], cycle_id, 'botw',
            botw_summary['metric'], botw_summary['title'],
            _parse_iso(botw_summary['startsAt']), _parse_iso(botw_summary['endsAt']),
        )
        await asyncio.to_thread(
            comp_db.upsert_competition,
            sotw_summary['id'], cycle_id, 'sotw',
            sotw_summary['metric'], sotw_summary['title'],
            _parse_iso(sotw_summary['startsAt']), _parse_iso(sotw_summary['endsAt']),
        )

        if botw_winner:
            await asyncio.to_thread(
                comp_db.set_competition_winner,
                botw_winner['competition_id'],
                botw_winner['wom_user_id'],
                botw_winner['gained'],
            )
        if sotw_winner:
            await asyncio.to_thread(
                comp_db.set_competition_winner,
                sotw_winner['competition_id'],
                sotw_winner['wom_user_id'],
                sotw_winner['gained'],
            )

        await asyncio.to_thread(comp_db.set_cycle_status, cycle_id, 'ended')

        draft = _build_draft(botw_winner, sotw_winner, conflicts)
        view = ResultsApprovalView()
        await mod_channel.send(draft, view=view)

        await mod_channel.send(
            '-# Reminder: collect picks from both winners before next Sunday '
            '(BOTW winner picks next SOTW; SOTW winner picks next BOTW).'
        )

    async def _resolve_winners(self, botw_summary, sotw_summary, mod_channel):
        """Fetch competition details and resolve winners.

        Falls back to the event-calendar parser if the WOM API is unavailable.
        Returns (botw_winner, sotw_winner, conflicts).
        """
        try:
            botw_detail = await asyncio.to_thread(wom_api.get_competition, botw_summary['id'])
            sotw_detail = await asyncio.to_thread(wom_api.get_competition, sotw_summary['id'])
            return winners.resolve_winners(botw_detail, sotw_detail)
        except Exception as api_exc:
            await mod_channel.send(
                f'WOM API failed fetching competition details: {api_exc}\nAttempting event-calendar fallback...'
            )

        try:
            botw_parsed, sotw_parsed = await self._event_calendar_fallback(botw_summary, sotw_summary)
            if botw_parsed or sotw_parsed:
                return winners.resolve_winners_from_fallback(
                    botw_parsed, sotw_parsed,
                    botw_summary['id'], sotw_summary['id'],
                )
        except Exception as fallback_exc:
            await mod_channel.send(f'Event-calendar fallback also failed: {fallback_exc}')

        await mod_channel.send(
            'Could not determine winners from WOM API or event-calendar. Resolve manually.'
        )
        return None, None, []

    async def _event_calendar_fallback(self, botw_summary, sotw_summary):
        """Read the event-calendar channel and match messages to the competition pair."""
        ec_id = os.getenv('EVENT_CALENDAR_CHANNEL')
        wom_bot_id_str = os.getenv('WOM_DISCORD_BOT_ID')
        if not ec_id or not wom_bot_id_str:
            return None, None

        ec_channel = self.bot.get_channel(int(ec_id))
        if not ec_channel:
            return None, None

        wom_bot_id = int(wom_bot_id_str)
        messages = await ec_channel.history(limit=50).flatten()
        wom_messages = [m for m in messages if m.author.id == wom_bot_id]

        botw_parsed = None
        sotw_parsed = None
        for msg in wom_messages:
            parsed = event_calendar.parse_result_message(msg)
            if parsed['competition_id'] == botw_summary['id']:
                botw_parsed = parsed
            elif parsed['competition_id'] == sotw_summary['id']:
                sotw_parsed = parsed

        return botw_parsed, sotw_parsed

    async def _ensure_cycle(self, botw_summary, existing_comp_row):
        """Return a cycle_id, creating a new cycle row if needed."""
        if existing_comp_row and existing_comp_row.get('cycle_id'):
            return existing_comp_row['cycle_id']

        starts_at = _parse_iso(botw_summary['startsAt'])
        ends_at = _parse_iso(botw_summary['endsAt'])
        return await asyncio.to_thread(comp_db.insert_cycle, starts_at, ends_at, 'planned')


# -------------------------------------------------------------------------
# Module-level helpers
# -------------------------------------------------------------------------

def _parse_iso(iso_str):
    """Parse an ISO-8601 UTC string from the WOM API into a naive UTC datetime."""
    return datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00')).replace(tzinfo=None)


def _build_draft(botw_winner, sotw_winner, conflicts):
    lines = [
        '**[DRAFT] Competition Results — Pending Mod Approval**',
        '',
        announcements.build_results_post(botw_winner, sotw_winner),
    ]
    if conflicts:
        lines += ['', '**Issues to resolve before approving:**']
        lines += [f'- {c}' for c in conflicts]
    lines += [
        '',
        '-# Click **Approve & Post** to publish to the announcements channel and swap winner roles.',
    ]
    return '\n'.join(lines)


def setup(bot):
    bot.add_cog(Competitions(bot))
