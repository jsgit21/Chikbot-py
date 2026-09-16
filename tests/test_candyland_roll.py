import pytest

from cogs.candyland import candyland_roll


def test_draw_minor_never_returns_an_excluded_id():
    pool = [{'id': 1}, {'id': 2}, {'id': 3}]
    for _ in range(200):
        drawn = candyland_roll.draw_minor(pool, {1, 2})
        assert drawn['id'] == 3


def test_draw_minor_always_returns_a_pool_member():
    pool = [{'id': 1}, {'id': 2}, {'id': 3}]
    for _ in range(200):
        drawn = candyland_roll.draw_minor(pool, set())
        assert drawn in pool


def test_draw_minor_raises_on_a_fully_excluded_pool():
    pool = [{'id': 1}, {'id': 2}]
    with pytest.raises(ValueError):
        candyland_roll.draw_minor(pool, {1, 2})


def test_draw_minor_single_item_pool_with_no_exclusions():
    pool = [{'id': 1}]
    assert candyland_roll.draw_minor(pool, set())['id'] == 1


def test_draw_minors_returns_the_requested_count_no_duplicates():
    pool = [{'id': i} for i in range(1, 6)]
    for _ in range(200):
        drawn = candyland_roll.draw_minors(pool, set(), 2)
        assert len(drawn) == 2
        assert drawn[0]['id'] != drawn[1]['id']
        assert all(d in pool for d in drawn)


def test_draw_minors_never_returns_an_excluded_id():
    pool = [{'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}]
    for _ in range(200):
        drawn = candyland_roll.draw_minors(pool, {1, 2}, 2)
        assert {d['id'] for d in drawn} == {3, 4}


def test_draw_minors_raises_when_not_enough_unexcluded_tasks():
    pool = [{'id': 1}, {'id': 2}, {'id': 3}]
    with pytest.raises(ValueError):
        candyland_roll.draw_minors(pool, {1, 2}, 2)


def test_draw_minor_delegates_to_draw_minors():
    pool = [{'id': 1}]
    assert candyland_roll.draw_minor(pool, set()) == candyland_roll.draw_minors(pool, set(), 1)[0]


def test_resolve_caller_team_matches_one_role():
    teams = [{'role_id': 10, 'name': 'A'}, {'role_id': 20, 'name': 'B'}]

    team, refusal = candyland_roll.resolve_caller_team(teams, {20, 99})

    assert refusal is None
    assert team['name'] == 'B'


def test_resolve_caller_team_no_role():
    teams = [{'role_id': 10, 'name': 'A'}]

    team, refusal = candyland_roll.resolve_caller_team(teams, {99})

    assert team is None
    assert refusal == candyland_roll.NO_TEAM


def test_resolve_caller_team_multiple_roles():
    teams = [{'role_id': 10, 'name': 'A'}, {'role_id': 20, 'name': 'B'}]

    team, refusal = candyland_roll.resolve_caller_team(teams, {10, 20})

    assert team is None
    assert refusal == candyland_roll.MULTI_TEAM


def test_blocking_condition_thread_ahead_of_board_is_out_of_sync():
    assert candyland_roll.blocking_condition(5, 3, 42) == candyland_roll.OUT_OF_SYNC


def test_blocking_condition_on_final_tile():
    assert candyland_roll.blocking_condition(42, 42, 42) == candyland_roll.FINAL_TILE


def test_blocking_condition_clear_to_roll():
    assert candyland_roll.blocking_condition(3, 3, 42) is None


def test_roll_move_is_1d4_plus_1_within_bounds():
    for _ in range(200):
        die, to_sequence = candyland_roll.roll_move(10, 42)
        assert 2 <= die <= 5
        assert to_sequence == 10 + die


def test_roll_move_clamps_to_final_tile():
    die, to_sequence = candyland_roll.roll_move(40, 42)
    assert to_sequence == 42


def test_roll_pair_advantage_keeps_higher():
    for _ in range(200):
        die_a, die_b, chosen = candyland_roll.roll_pair('ADVANTAGE')
        assert 2 <= die_a <= 5
        assert 2 <= die_b <= 5
        assert chosen == max(die_a, die_b)


def test_roll_pair_disadvantage_keeps_lower():
    for _ in range(200):
        die_a, die_b, chosen = candyland_roll.roll_pair('DISADVANTAGE')
        assert 2 <= die_a <= 5
        assert 2 <= die_b <= 5
        assert chosen == min(die_a, die_b)


def test_catchup_move_no_second_wind_within_five_of_the_leader():
    # ordinary roll lands 4 behind the leader -> no bonus die
    for _ in range(200):
        die, to_sequence, band = candyland_roll.catchup_move(30, 5, 39, 65)
        assert die == 5
        assert to_sequence == 35
        assert band is None


def test_catchup_move_no_second_wind_when_ordinary_roll_reaches_the_leader():
    for _ in range(200):
        die, to_sequence, band = candyland_roll.catchup_move(38, 5, 41, 65)
        assert die == 5
        assert to_sequence == 43  # past the leader on 41, ordinary roll stands
        assert band is None


def test_catchup_modifier_table():
    assert candyland_roll.catchup_modifier(4) is None
    assert candyland_roll.catchup_modifier(5) == 1
    assert candyland_roll.catchup_modifier(7) == 1
    assert candyland_roll.catchup_modifier(8) == 2
    assert candyland_roll.catchup_modifier(13) == 3
    assert candyland_roll.catchup_modifier(19) == 5
    assert candyland_roll.catchup_modifier(20) == 6
    assert candyland_roll.catchup_modifier(42) == 6  # capped


def test_catchup_move_small_gap_is_1d4_plus_1():
    # from 30, ordinary 2 -> lands 32, leader 40: gap 8 -> modifier 2
    for _ in range(200):
        die, to_sequence, second_wind = candyland_roll.catchup_move(30, 2, 40, 65)
        assert 5 <= die <= 8            # 2 + (2 + 1..4)
        assert second_wind == 2
        assert to_sequence == min(30 + die, 39)


def test_catchup_move_far_gap_is_capped():
    # from 10, ordinary 2 -> lands 12, leader 40: gap 28 -> modifier capped at 6
    for _ in range(200):
        die, to_sequence, second_wind = candyland_roll.catchup_move(10, 2, 40, 65)
        assert 9 <= die <= 12           # 2 + (6 + 1..4)
        assert second_wind == 6
        assert to_sequence == 10 + die  # far below leader - 1, unclamped


def test_catchup_move_end_gap_never_worsens_as_starting_gap_grows():
    # best/worst/avg end gap after the second wind must be monotonically
    # non-decreasing as the starting gap grows - no band-edge inversions.
    prev = None
    for gap in range(5, 46):
        modifier = candyland_roll.catchup_modifier(gap)
        ends = [max(1, gap - (roll + modifier)) for roll in range(1, 5)]
        current = (min(ends), max(ends), sum(ends) / len(ends))
        if prev is not None:
            assert all(c >= p for c, p in zip(current, prev)), gap
        prev = current


def test_catchup_move_never_lands_level_with_or_past_the_leader():
    # from 30, ordinary 2 -> lands 32, leader 38 (gap 6, 1d4+1 band); totals
    # 4..7 reach 34..37, clamp to 37 (leader - 1) when it would reach 38+
    for _ in range(200):
        die, to_sequence, band = candyland_roll.catchup_move(30, 2, 38, 65)
        assert to_sequence <= 37
        assert to_sequence == min(30 + die, 37)


def test_catchup_move_respects_the_board_end():
    for _ in range(200):
        die, to_sequence, band = candyland_roll.catchup_move(55, 3, 66, 65)
        assert to_sequence == min(55 + die, 65)
