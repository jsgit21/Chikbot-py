from cogs.candyland import candyland_format


def test_header_prepends_team():
    result = candyland_format.header('@Reds', 'has completed Tile 3')

    assert result == '# Team @Reds\n-# has completed Tile 3'


def test_roll_announcement_basic_shape():
    result = candyland_format.roll_announcement(
        '@Reds', 'RED', '@Nick', 3, 4, 'ART', new_thread_id=900,
    )

    assert result.startswith('# Team @Reds\n-# RED has completed Tile 3')
    assert '🎲 @Nick has rolled a....' in result
    assert 'ART' in result
    assert "Your team's next tile is ➡️ <#900>" in result


def test_roll_announcement_modifier_tag():
    result = candyland_format.roll_announcement(
        '@Reds', 'RED', '@Nick', 3, 4, 'ART', modifier_name='Advantage',
    )

    assert '🎲 @Nick has rolled a.... _(with Advantage)_' in result


def test_roll_announcement_final_tile_has_no_next_tile_line():
    result = candyland_format.roll_announcement(
        '@Reds', 'RED', '@Nick', 40, 5, 'ART', new_thread_id=900, final=True,
    )

    assert '-# 🏁 This is the **final tile**.' in result
    assert 'next tile' not in result.lower()


def test_bounty_taken_shape():
    result = candyland_format.bounty_taken(
        '@Reds', '@Nick', 'Retreat', 'your team must get 2 items.', 'move back 1 tile.',
    )

    assert '### The **Retreat** bounty has been redeemed.' in result
    assert '-# This means that your team must get 2 items.' in result
    assert '-# move back 1 tile.' in result


def test_bounty_claimed_shape():
    result = candyland_format.bounty_claimed(
        '@Reds', '@Nick', 'Retreat', 'move back 1 tile.', 901,
    )

    assert '### move back 1 tile.' in result
    assert "Your team's next tile is ➡️ <#901>" in result


def test_bounties_list_strikes_used_bounties():
    rows = [('RETREAT', 'Retreat', True), ('ADVANCE', 'Advance', False)]

    result = candyland_format.bounties_list('@Reds', rows)

    assert '~~Retreat~~' in result
    assert '**Advance**' in result
    assert '~~Advance~~' not in result


def test_final_tile_doomsday_cue_stays_non_spoiling():
    result = candyland_format.final_tile('@Reds', 'RED', '@Planner', '@Mod', claim=False)

    assert 'has completed the final tile.' in result
    assert '— the road ends here.' in result
    assert 'Board 2' not in result


def test_final_tile_claim_asks_for_verification():
    result = candyland_format.final_tile('@Reds', 'RED', '@Planner', '@Mod', claim=True)

    assert 'has claimed the final tile.' in result
    assert '— verify this claim.' in result


def test_manual_move_notes_cleared_bounty():
    result = candyland_format.manual_move('@Reds', 5, 20, bounty_cleared=True)

    assert 'moved from tile 5 to 20 by a moderator.' in result
    assert 'outstanding bounty was cleared' in result


def test_manual_move_without_bounty_cleared():
    result = candyland_format.manual_move('@Reds', 5, 20, bounty_cleared=False)

    assert 'outstanding bounty was cleared' not in result
