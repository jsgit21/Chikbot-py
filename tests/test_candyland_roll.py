from cogs.candyland import candyland_roll


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


def test_catchup_move_no_catchup_when_ordinary_roll_lands_within_two():
    # gap of exactly 2 after the ordinary roll -> no extra die
    for _ in range(200):
        die, to_sequence = candyland_roll.catchup_move(30, 5, 37, 65)
        assert die == 5
        assert to_sequence == 35


def test_catchup_move_no_catchup_when_ordinary_roll_reaches_or_passes_blocker():
    for _ in range(200):
        die, to_sequence = candyland_roll.catchup_move(38, 4, 41, 65)
        assert die == 4
        assert to_sequence == 42  # past the blocker on 41, ordinary roll stands


def test_catchup_move_adds_a_die_when_still_more_than_two_behind():
    # from 10, ordinary 3 -> lands 13, blocker 40: gap 27, always catches up
    for _ in range(200):
        die, to_sequence = candyland_roll.catchup_move(10, 3, 40, 65)
        assert 5 <= die <= 8            # 3 + (2..5)
        assert to_sequence == 10 + die  # well below blocker - 1, unclamped


def test_catchup_move_never_lands_level_with_or_past_the_blocker():
    # from 10, ordinary 3 -> lands 13 (gap 5, catches up); totals 5..8 reach
    # 15..18, so it clamps to 17 (blocker - 1) whenever it would reach 18+
    for _ in range(200):
        die, to_sequence = candyland_roll.catchup_move(10, 3, 18, 65)
        assert to_sequence <= 17
        assert to_sequence == min(10 + die, 17)


def test_catchup_move_respects_the_board_end():
    for _ in range(200):
        die, to_sequence = candyland_roll.catchup_move(55, 3, 66, 65)
        assert to_sequence == min(55 + die, 65)
