"""Tests for Phase 2/3 pure-logic modules: winners, event_calendar, announcements.

No network, no clock, no DB in this file. All DB calls in winners.py are
isolated by passing testdb=None and replacing identity_db calls with mocks
where needed (see test_resolve_winner_* below).
"""
import datetime
import unittest.mock as mock

import pytest

from cogs.wise_old_man.competitions import announcements, event_calendar, types, wom_api, winners


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_participation(player_id, display_name, gained):
    return {
        'player': {'id': player_id, 'displayName': display_name},
        'progress': {'gained': gained, 'start': 0, 'end': gained},
    }


def _make_competition_detail(comp_id, participations):
    return {
        'id': comp_id,
        'participations': participations,
    }


# ---------------------------------------------------------------------------
# winners._winner_from_participations
# ---------------------------------------------------------------------------

def test_winner_from_participations_returns_max():
    parts = [
        _make_participation(1, 'Alpha', 500),
        _make_participation(2, 'Beta', 1200),
        _make_participation(3, 'Gamma', 800),
    ]
    result = winners._winner_from_participations(parts)
    assert result['player']['displayName'] == 'Beta'


def test_winner_from_participations_skips_none_gained():
    parts = [
        _make_participation(1, 'Alpha', None),
        _make_participation(2, 'Beta', 300),
    ]
    result = winners._winner_from_participations(parts)
    assert result['player']['displayName'] == 'Beta'


def test_winner_from_participations_all_none_returns_none():
    parts = [_make_participation(1, 'Alpha', None)]
    assert winners._winner_from_participations(parts) is None


def test_winner_from_participations_empty_returns_none():
    assert winners._winner_from_participations([]) is None


# ---------------------------------------------------------------------------
# winners.resolve_winner (mocking identity DB)
# ---------------------------------------------------------------------------

def _make_linked_identity(user_id, alias=None):
    return {'user_id': user_id, 'preferred_alias': alias}


def test_resolve_winner_linked(monkeypatch):
    monkeypatch.setattr(
        'cogs.wise_old_man.identity.db.discord_user_for_wom_id',
        lambda wid, testdb=None: _make_linked_identity(42, 'mayo'),
    )
    detail = _make_competition_detail(10, [_make_participation(100, 'spoiled mayo', 5000)])
    result = winners.resolve_winner(detail)

    assert result['competition_id'] == 10
    assert result['wom_user_id'] == 100
    assert result['rsn'] == 'spoiled mayo'
    assert result['gained'] == 5000
    assert result['discord_user_id'] == 42
    assert result['alias'] == 'mayo'


def test_resolve_winner_unlinked(monkeypatch):
    monkeypatch.setattr(
        'cogs.wise_old_man.identity.db.discord_user_for_wom_id',
        lambda wid, testdb=None: None,
    )
    detail = _make_competition_detail(11, [_make_participation(101, 'peppy x', 3000)])
    result = winners.resolve_winner(detail)

    assert result['discord_user_id'] is None
    assert result['alias'] is None


def test_resolve_winner_no_participations(monkeypatch):
    monkeypatch.setattr(
        'cogs.wise_old_man.identity.db.discord_user_for_wom_id',
        lambda wid, testdb=None: None,
    )
    detail = _make_competition_detail(12, [])
    assert winners.resolve_winner(detail) is None


# ---------------------------------------------------------------------------
# event_calendar parsing
# ---------------------------------------------------------------------------

def _make_message(content='', embed_texts=None):
    """Build a minimal mock discord.Message."""
    msg = mock.MagicMock()
    msg.content = content

    embeds = []
    for text in (embed_texts or []):
        embed = mock.MagicMock()
        embed.title = text.get('title')
        embed.url = text.get('url')
        embed.description = text.get('description')
        embed.fields = []
        embeds.append(embed)
    msg.embeds = embeds
    return msg


def test_event_calendar_extracts_comp_id_from_content():
    msg = _make_message(content='Results: https://wiseoldman.net/competitions/9999')
    result = event_calendar.parse_result_message(msg)
    assert result['competition_id'] == 9999


def test_event_calendar_extracts_comp_id_from_embed_url():
    msg = _make_message(embed_texts=[{'url': 'https://wiseoldman.net/competitions/1234'}])
    result = event_calendar.parse_result_message(msg)
    assert result['competition_id'] == 1234


def test_event_calendar_extracts_winner_from_description():
    desc = '1. spoiled mayo — 5,000\n2. peppy x — 3,000'
    msg = _make_message(embed_texts=[
        {'url': 'https://wiseoldman.net/competitions/42', 'description': desc}
    ])
    result = event_calendar.parse_result_message(msg)
    assert result['winner_rsn'] == 'spoiled mayo'
    assert result['winner_gained'] == 5000


def test_event_calendar_no_comp_id_returns_none():
    msg = _make_message(content='Some random message')
    result = event_calendar.parse_result_message(msg)
    assert result['competition_id'] is None


def test_event_calendar_no_participants_returns_none_winner():
    msg = _make_message(embed_texts=[{'url': 'https://wiseoldman.net/competitions/99'}])
    result = event_calendar.parse_result_message(msg)
    assert result['winner_rsn'] is None
    assert result['winner_gained'] is None


# ---------------------------------------------------------------------------
# announcements.build_result_post
# ---------------------------------------------------------------------------

def _winner(comp_type, rsn, gained, discord_user_id=None, alias=None):
    return {
        'competition_id': 1,
        'wom_user_id': 100,
        'rsn': rsn,
        'gained': gained,
        'discord_user_id': discord_user_id,
        'alias': alias,
    }


def test_build_result_post_linked_winner():
    bw = _winner('botw', 'crab', 250, discord_user_id=1234)
    text = announcements.build_result_post(types.TYPES['botw'], bw)

    assert '**BOTW Results**' in text
    assert '<@1234>' in text
    assert '250 KC' in text


def test_build_result_post_unlinked_winner():
    sw = _winner('sotw', 'mayo', 500000)
    text = announcements.build_result_post(types.TYPES['sotw'], sw)

    assert '**SOTW Results**' in text
    assert '@mayo' in text
    assert '500,000 XP' in text


def test_build_result_post_none_winner():
    text = announcements.build_result_post(types.TYPES['botw'], None)
    assert 'No winner data available.' in text


# ---------------------------------------------------------------------------
# announcements.build_kickoff_post
# ---------------------------------------------------------------------------

def _pick(title, metric_display, picker_text):
    return {'title': title, 'metric_display': metric_display, 'picker_text': picker_text}


def test_build_kickoff_post_includes_titles_and_pickers():
    botw = _pick("Vorkath - Boss of the Week [mayo's pick]", 'Vorkath', '<@1234>')
    sotw = _pick("Runecrafting - Skill of the Week [crab's pick]", 'Runecrafting', '@peppy')
    starts_at = datetime.datetime(2026, 7, 4, 10, 0)  # 10:00 ET
    ends_at = datetime.datetime(2026, 7, 6, 0, 0)     # 00:00 ET

    text = announcements.build_kickoff_post(starts_at, ends_at, botw, sotw)

    assert "Vorkath - Boss of the Week [mayo's pick]" in text
    assert "Runecrafting - Skill of the Week [crab's pick]" in text
    assert '<@1234>' in text
    assert '@peppy' in text
    assert 'Sat 7/4 10:00 AM' in text
    assert 'Mon 7/6 12:00 AM ET' in text


# ---------------------------------------------------------------------------
# wom_api.find_ended_competitions
# ---------------------------------------------------------------------------

_NOW = datetime.datetime(2026, 7, 6, 12, 0, tzinfo=datetime.timezone.utc)


def _make_comp_summary(comp_id, title, starts_at, ends_at):
    return {'id': comp_id, 'title': title, 'startsAt': starts_at, 'endsAt': ends_at}


def test_find_ended_competitions_includes_recently_ended():
    current_window = ('2026-06-27T14:00:00.000Z', '2026-07-04T14:00:00.000Z')
    current_botw = _make_comp_summary(2, 'Vorkath - Boss of the Week', *current_window)
    current_sotw = _make_comp_summary(3, 'Fishing - Skill of the Week', *current_window)

    result = wom_api.find_ended_competitions([current_botw, current_sotw], now=_NOW)

    assert {c['id'] for c in result} == {2, 3}


def test_find_ended_competitions_missing_keys_does_not_crash():
    incomplete = {}  # no title, endsAt, startsAt
    result = wom_api.find_ended_competitions([incomplete], now=_NOW)

    assert result == []


def test_find_ended_competitions_ignores_not_yet_ended():
    not_ended = _make_comp_summary(
        1, 'Vorkath - Boss of the Week', '2026-07-04T14:00:00.000Z', '2026-07-13T04:00:00.000Z'
    )
    result = wom_api.find_ended_competitions([not_ended], now=_NOW)

    assert result == []


def test_find_ended_competitions_ignores_stray_past_lookback():
    old_window = ('2026-05-01T14:00:00.000Z', '2026-05-08T14:00:00.000Z')
    stray = _make_comp_summary(1, 'Runecrafting - Skill of the Week', *old_window)

    result = wom_api.find_ended_competitions([stray], now=_NOW, lookback_days=14)

    assert result == []
