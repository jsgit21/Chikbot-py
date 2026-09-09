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


def test_roll_move_extra_die_no_modifier_is_4_to_10():
    for _ in range(200):
        die, _ = candyland_roll.roll_move(10, 65, extra_die=True)
        assert 4 <= die <= 10


def test_roll_move_extra_die_stacks_with_double_down():
    for _ in range(200):
        die, _ = candyland_roll.roll_move(10, 65, 'DOUBLE_DOWN', extra_die=True)
        assert 6 <= die <= 15


def test_roll_move_extra_die_stacks_with_advantage_and_disadvantage():
    # min/max of two 1d4+1 is still 2..5, so with the extra 1d4+1 both land in
    # 4..10 (the modifier only skews the distribution, not the bounds).
    for _ in range(200):
        adv, _ = candyland_roll.roll_move(10, 65, 'ADVANTAGE', extra_die=True)
        dis, _ = candyland_roll.roll_move(10, 65, 'DISADVANTAGE', extra_die=True)
        assert 4 <= adv <= 10
        assert 4 <= dis <= 10


def test_roll_move_catchup_clamps_to_ceiling_on_overshoot():
    for _ in range(200):
        _, to_sequence = candyland_roll.roll_move(20, 65, ceiling=23, extra_die=True)
        assert to_sequence == 23


def test_roll_move_catchup_below_ceiling_is_unclamped():
    die, to_sequence = candyland_roll.roll_move(5, 65, ceiling=60, extra_die=True)
    assert to_sequence == 5 + die


def test_roll_move_ceiling_above_board_size_does_not_raise_board_clamp():
    _, to_sequence = candyland_roll.roll_move(40, 42, ceiling=100, extra_die=True)
    assert to_sequence == 42


def test_roll_move_no_extra_die_no_ceiling_behaves_as_before():
    for _ in range(200):
        die, to_sequence = candyland_roll.roll_move(10, 42)
        assert 2 <= die <= 5
        assert to_sequence == 10 + die
