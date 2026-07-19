"""Tests for competitionscog.py's pure-ish logic: the nominator-resolution fix and
the _build_side helper. No network, no clock, no live DB -- identity_db and comp_db
calls are monkeypatched at the boundary.
"""
import datetime
import unittest.mock as mock

import pytest

from cogs.wise_old_man.competitions import types
from cogs.wise_old_man.competitions.competitionscog import Competitions


def _make_cog():
    return Competitions.__new__(Competitions)  # bypass __init__ (no bot instance needed)


@pytest.mark.asyncio
async def test_resolve_nominator_no_partner_type_defaults_to_group(monkeypatch):
    monkeypatch.setattr(
        'cogs.wise_old_man.competitions.competitionscog.types.nominator_source_for',
        lambda comp_type_key: None,
    )
    cog = _make_cog()
    user_id, alias = await cog._resolve_nominator(
        guild=mock.MagicMock(), explicit_member=None,
        last_cycle={'id': 1, 'ends_at': datetime.datetime(2026, 7, 6)},
        comp_type='boss_rush',
    )
    assert user_id is None
    assert alias == 'the group'


@pytest.mark.asyncio
async def test_build_side_fresh_title(monkeypatch):
    cog = _make_cog()
    monkeypatch.setattr(
        cog, '_resolve_nominator',
        mock.AsyncMock(return_value=(1234, 'mayo')),
    )
    side = await cog._build_side(
        guild=mock.MagicMock(), comp_type_key='botw', metric='vorkath',
        explicit_member=None, last_cycle=None,
    )
    assert side['title'] == "Vorkath - Boss of the Week [mayo's pick]"
    assert side['nominator_user_id'] == 1234
    assert side['nominator_text'] == '<@1234>'
    assert side['existing_competition_id'] is None


@pytest.mark.asyncio
async def test_build_side_resumed_title_and_nominator(monkeypatch):
    cog = _make_cog()
    monkeypatch.setattr(
        cog, '_resolve_nominator',
        mock.AsyncMock(return_value=(1234, 'mayo')),
    )
    existing_row = {'nominator_user_id': 5678, 'competition_id': 42, 'verification_code': 'abc'}
    existing_detail = {'title': 'Vorkath - Boss of the Week [existing]', 'metric': 'vorkath'}
    side = await cog._build_side(
        guild=mock.MagicMock(), comp_type_key='botw', metric='vorkath',
        explicit_member=None, last_cycle=None,
        existing_row=existing_row, existing_detail=existing_detail,
    )
    assert side['title'] == 'Vorkath - Boss of the Week [existing]'
    assert side['nominator_user_id'] == 5678  # from existing_row, not the freshly-resolved 1234
    assert side['existing_competition_id'] == 42
    assert side['existing_verification_code'] == 'abc'
