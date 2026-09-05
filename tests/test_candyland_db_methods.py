import pytest
import pymysql
from database import db_methods
from cogs.candyland import candyland_board
from cogs.candyland import candyland_bounty
from cogs.candyland import candyland_db_methods as candyland_methods

TEST_DATABASE = 'candyland_test'
SOURCE_DATABASE = 'candyland'

# Child-before-parent for drops, parent-before-child for creates.
TABLES = [
    'bounty',
    'bounty_use',
    'tile_thread',
    'movement',
    'team_state',
    'team',
    'event',
]


@pytest.fixture(scope='module')
def test_db():
    db = db_methods.create_connection(database=TEST_DATABASE)
    yield db
    db.close()


@pytest.fixture
def setup_candyland_tables(test_db):
    cursor = test_db.cursor()

    for table in TABLES:
        cursor.execute(f'drop table if exists {TEST_DATABASE}.{table}')
    for table in reversed(TABLES):
        cursor.execute(f'create table {TEST_DATABASE}.{table} like {SOURCE_DATABASE}.{table}')


def test_create_and_get_event(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('cgl-2026', None, None, testdb=test_db)
    event = candyland_methods.get_event('cgl-2026', testdb=test_db)

    assert event['id'] == event_id
    assert event['slug'] == 'cgl-2026'
    assert event['status'] == 'setup'


def test_register_team_is_idempotent(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('cgl-2026', None, None, testdb=test_db)

    first = candyland_methods.register_team(event_id, 'Team 1', 111, 222, 0, testdb=test_db)
    second = candyland_methods.register_team(event_id, 'Team 1 renamed', 111, 999, 0, testdb=test_db)

    assert first == second

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f'select * from {TEST_DATABASE}.team where event_id = %s', (event_id,))
    teams = cursor.fetchall()

    assert len(teams) == 1
    assert teams[0]['name'] == 'Team 1 renamed'
    assert teams[0]['forum_channel_id'] == 999

    cursor.execute(
        f'select count(*) as n from {TEST_DATABASE}.team_state where team_id = %s',
        (first,),
    )
    assert cursor.fetchone()['n'] == 1


def test_replay_folds_to_last_movement():
    movements = [
        {'to_sequence': 4},
        {'to_sequence': 3},    # adjustment
        {'to_sequence': 43},   # crossover past the final Board 1 tile
    ]

    assert candyland_methods._replay(movements) == 43


def test_refold_team_state_writes_fold(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('cgl-2026', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Team 1', 111, 222, 0, testdb=test_db)

    candyland_methods.record_movement(team_id, 'roll', 3, 1, 4, None, None, None, testdb=test_db)
    candyland_methods.record_movement(team_id, 'adjustment', None, 4, 3, None, None, 'fix', testdb=test_db)
    last_id = candyland_methods.record_movement(team_id, 'board_transition', None, 3, 43, None, None, None, testdb=test_db)

    state = candyland_methods.refold_team_state(team_id, testdb=test_db)

    assert state['current_sequence'] == 43
    assert state['last_movement_id'] == last_id


def test_get_active_event_returns_the_single_live_row(test_db, setup_candyland_tables):
    candyland_methods.create_event('past', None, None, testdb=test_db)
    live_id = candyland_methods.create_event('now', None, None, testdb=test_db)

    assert candyland_methods.get_active_event(testdb=test_db) is None

    candyland_methods.set_event_status('now', 'live', testdb=test_db)
    active = candyland_methods.get_active_event(testdb=test_db)
    assert active['id'] == live_id
    assert active['slug'] == 'now'


def test_advance_team_by_roll_appends_and_folds(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)

    movement_id = candyland_methods.advance_team_by_roll(
        team_id, 3, 1, 4, 999, 42, None, testdb=test_db
    )
    assert movement_id is not None

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == 4
    assert state['last_movement_id'] == movement_id


def test_advance_team_by_roll_rejects_a_stale_guard(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)

    first = candyland_methods.advance_team_by_roll(
        team_id, 3, 1, 4, 999, 42, None, testdb=test_db
    )
    # a second roll that still thinks last_movement_id is NULL has lost the race
    second = candyland_methods.advance_team_by_roll(
        team_id, 5, 1, 6, 999, 42, None, testdb=test_db
    )
    assert second is None

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == 4
    assert state['last_movement_id'] == first

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f'select count(*) as n from {TEST_DATABASE}.movement where team_id = %s', (team_id,))
    assert cursor.fetchone()['n'] == 1


def test_get_any_thread_returns_latest_regardless_of_state(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)

    assert candyland_methods.get_any_thread(team_id, testdb=test_db) is None

    first_id = candyland_methods.open_tile_thread(team_id, 1, 900, testdb=test_db)
    candyland_methods.close_tile_thread(first_id, testdb=test_db)

    latest = candyland_methods.get_any_thread(team_id, testdb=test_db)
    assert latest['id'] == first_id
    assert latest['state'] == 'closed'


def test_swap_open_thread_moves_the_single_open_row(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    old_id = candyland_methods.open_tile_thread(team_id, 1, 900, testdb=test_db)

    candyland_methods.swap_open_thread(team_id, 4, 901, old_id, testdb=test_db)

    open_row = candyland_methods.get_open_thread(team_id, testdb=test_db)
    assert open_row['tile_sequence'] == 4
    assert open_row['thread_id'] == 901

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f"select count(*) as n from {TEST_DATABASE}.tile_thread "
                   f"where team_id = %s and state = 'open'", (team_id,))
    assert cursor.fetchone()['n'] == 1


def test_move_open_thread_to_tile_repoints_an_existing_row(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    old = candyland_methods.open_tile_thread(team_id, 7, 700, testdb=test_db)
    candyland_methods.close_tile_thread(old, testdb=test_db)
    candyland_methods.open_tile_thread(team_id, 8, 800, testdb=test_db)

    candyland_methods.move_open_thread_to_tile(team_id, 7, 701, testdb=test_db)

    open_row = candyland_methods.get_open_thread(team_id, testdb=test_db)
    assert open_row['id'] == old
    assert open_row['tile_sequence'] == 7
    assert open_row['thread_id'] == 701

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f"select count(*) as n from {TEST_DATABASE}.tile_thread "
                   f"where team_id = %s and state = 'open'", (team_id,))
    assert cursor.fetchone()['n'] == 1


def test_move_open_thread_to_tile_same_tile_swaps_thread_id(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    row_id = candyland_methods.open_tile_thread(team_id, 5, 500, testdb=test_db)

    candyland_methods.move_open_thread_to_tile(team_id, 5, 501, testdb=test_db)

    open_row = candyland_methods.get_open_thread(team_id, testdb=test_db)
    assert open_row['id'] == row_id
    assert open_row['tile_sequence'] == 5
    assert open_row['thread_id'] == 501


def test_move_open_thread_to_tile_inserts_for_a_new_tile(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.open_tile_thread(team_id, 8, 800, testdb=test_db)

    candyland_methods.move_open_thread_to_tile(team_id, 9, 900, testdb=test_db)

    open_row = candyland_methods.get_open_thread(team_id, testdb=test_db)
    assert open_row['tile_sequence'] == 9
    assert open_row['thread_id'] == 900

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f'select count(*) as n from {TEST_DATABASE}.tile_thread where team_id = %s',
                   (team_id,))
    assert cursor.fetchone()['n'] == 2


def test_clear_event_teams_drops_teams_and_cascades(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.set_event_status('e', 'live', testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 3, 1, 4, 900, 42, None, testdb=test_db)
    candyland_methods.open_tile_thread(team_id, 4, 901, testdb=test_db)

    candyland_methods.clear_event_teams(event_id, testdb=test_db)

    assert candyland_methods.get_event('e', testdb=test_db)['status'] == 'setup'
    assert candyland_methods.get_teams(event_id, testdb=test_db) == []

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    for table in ('movement', 'tile_thread', 'team_state'):
        cursor.execute(
            f'select count(*) as n from {TEST_DATABASE}.{table} where team_id = %s',
            (team_id,),
        )
        assert cursor.fetchone()['n'] == 0


def test_clear_event_teams_leaves_other_events_intact(test_db, setup_candyland_tables):
    keep_id = candyland_methods.create_event('keep', None, None, testdb=test_db)
    candyland_methods.register_team(keep_id, 'Keepers', 111, 222, 0, testdb=test_db)
    drop_id = candyland_methods.create_event('drop', None, None, testdb=test_db)
    candyland_methods.register_team(drop_id, 'Droppers', 333, 444, 0, testdb=test_db)

    candyland_methods.clear_event_teams(drop_id, testdb=test_db)

    assert [t['name'] for t in candyland_methods.get_teams(keep_id, testdb=test_db)] == ['Keepers']
    assert candyland_methods.get_teams(drop_id, testdb=test_db) == []
    assert candyland_methods.get_event('keep', testdb=test_db)['status'] == 'setup'


def test_get_all_tile_threads_returns_only_event_threads(test_db, setup_candyland_tables):
    event_a = candyland_methods.create_event('a', None, None, testdb=test_db)
    team_a = candyland_methods.register_team(event_a, 'Reds', 11, 12, 0, testdb=test_db)
    candyland_methods.open_tile_thread(team_a, 3, 900, testdb=test_db)

    event_b = candyland_methods.create_event('b', None, None, testdb=test_db)
    team_b = candyland_methods.register_team(event_b, 'Blues', 21, 22, 0, testdb=test_db)
    candyland_methods.open_tile_thread(team_b, 5, 901, testdb=test_db)

    rows = candyland_methods.get_all_tile_threads(event_a, testdb=test_db)

    assert len(rows) == 1
    assert rows[0]['team_id'] == team_a
    assert rows[0]['thread_id'] == 900
    assert rows[0]['tile_sequence'] == 3


def test_get_all_state_one_row_per_team_in_sort_order(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('cgl-2026', None, None, testdb=test_db)
    candyland_methods.register_team(event_id, 'Bravo', 20, 21, 1, testdb=test_db)
    candyland_methods.register_team(event_id, 'Alpha', 10, 11, 0, testdb=test_db)
    candyland_methods.register_team(event_id, 'Charlie', 30, 31, 2, testdb=test_db)

    rows = candyland_methods.get_all_state(event_id, testdb=test_db)

    assert [r['name'] for r in rows] == ['Alpha', 'Bravo', 'Charlie']
    assert all(r['current_sequence'] == 1 for r in rows)


def test_board_of_boundaries():
    assert candyland_board.board_of(1) == 1
    assert candyland_board.board_of(candyland_board.BOARD1_SIZE) == 1
    assert candyland_board.board_of(candyland_board.BOARD1_SIZE + 1) == 2
    assert candyland_board.board_of(candyland_board.TOTAL_TILES) == 2


def test_board_edge_tiles():
    b1_last = candyland_board.BOARD1_SIZE
    b2_first = candyland_board.BOARD1_SIZE + 1
    b2_last = candyland_board.TOTAL_TILES
    for seq in (1, b1_last, b2_first, b2_last):
        assert candyland_board.is_board_edge_tile(seq)
    for seq in (2, b1_last - 1, b2_first + 1, b2_last - 1):
        assert not candyland_board.is_board_edge_tile(seq)


def test_take_bounty_does_not_move_team(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)

    result = candyland_methods.take_bounty(
        team_id, 'RETREAT', 42, state['last_movement_id'], testdb=test_db
    )

    assert result['ok']
    assert result['from_sequence'] == 5

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == 5

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        f"select * from {TEST_DATABASE}.movement where team_id = %s and kind = 'adjustment'",
        (team_id,),
    )
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]['from_sequence'] == 5
    assert rows[0]['to_sequence'] == 5

    cursor.execute(f'select * from {TEST_DATABASE}.bounty_use where team_id = %s', (team_id,))
    bounty_rows = cursor.fetchall()
    assert len(bounty_rows) == 1
    assert bounty_rows[0]['board_number'] == 1
    assert bounty_rows[0]['used_on_sequence'] == 5
    assert bounty_rows[0]['claimed_at'] is None


def test_complete_bounty_retreat_moves_team_back(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.take_bounty(team_id, 'RETREAT', 42, state['last_movement_id'], testdb=test_db)
    unclaimed = candyland_methods.get_unclaimed_bounty(team_id, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)

    result = candyland_methods.complete_bounty(
        team_id, unclaimed['id'], 42, state['last_movement_id'], testdb=test_db
    )

    assert result['ok']
    assert result['moved']
    assert result['from_sequence'] == 5
    assert result['to_sequence'] == 4

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == 4

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        f"select * from {TEST_DATABASE}.movement where team_id = %s and kind = 'adjustment' order by id",
        (team_id,),
    )
    rows = cursor.fetchall()
    assert len(rows) == 2  # the take marker, then the claim's actual move
    assert rows[-1]['from_sequence'] == 5 and rows[-1]['to_sequence'] == 4

    cursor.execute(
        f'select claimed_at from {TEST_DATABASE}.bounty_use where id = %s',
        (unclaimed['id'],),
    )
    assert cursor.fetchone()['claimed_at'] is not None


def test_complete_bounty_advance_moves_team_forward(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.take_bounty(team_id, 'ADVANCE', 42, state['last_movement_id'], testdb=test_db)
    unclaimed = candyland_methods.get_unclaimed_bounty(team_id, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)

    result = candyland_methods.complete_bounty(
        team_id, unclaimed['id'], 42, state['last_movement_id'], testdb=test_db
    )

    assert result['moved']
    assert result['to_sequence'] == 6

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == 6


def test_complete_bounty_modifier_writes_no_movement_row(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.take_bounty(team_id, 'DISADVANTAGE', 42, state['last_movement_id'], testdb=test_db)
    unclaimed = candyland_methods.get_unclaimed_bounty(team_id, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)

    result = candyland_methods.complete_bounty(
        team_id, unclaimed['id'], 42, state['last_movement_id'], testdb=test_db
    )

    assert result['moved'] is False
    assert result['movement_id'] is None
    assert result['from_sequence'] == result['to_sequence'] == 5

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == 5

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        f"select count(*) as n from {TEST_DATABASE}.movement where team_id = %s and kind = 'adjustment'",
        (team_id,),
    )
    # only the take marker; complete_bounty wrote no second row
    assert cursor.fetchone()['n'] == 1


def test_get_unclaimed_bounty_returns_most_recent_unclaimed(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)

    assert candyland_methods.get_unclaimed_bounty(team_id, testdb=test_db) is None

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.take_bounty(team_id, 'SWAP', 42, state['last_movement_id'], testdb=test_db)

    unclaimed = candyland_methods.get_unclaimed_bounty(team_id, testdb=test_db)
    assert unclaimed['bounty_key'] == 'SWAP'
    assert unclaimed['claimed_at'] is None

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.complete_bounty(
        team_id, unclaimed['id'], 42, state['last_movement_id'], testdb=test_db
    )

    assert candyland_methods.get_unclaimed_bounty(team_id, testdb=test_db) is None


def test_bounty_destination_clamps():
    assert candyland_bounty.destination('RETREAT', 1, 42) == 1
    assert candyland_bounty.destination('RETREAT', 5, 42) == 4
    assert candyland_bounty.destination('ADVANCE', 42, 42) == 42
    assert candyland_bounty.destination('ADVANCE', 5, 42) == 6
    assert candyland_bounty.destination('DISADVANTAGE', 5, 42) == 5


def test_take_bounty_duplicate_refused(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)

    first = candyland_methods.take_bounty(
        team_id, 'SWAP', 42, state['last_movement_id'], testdb=test_db
    )
    assert first['ok']

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    second = candyland_methods.take_bounty(
        team_id, 'SWAP', 42, state['last_movement_id'], testdb=test_db
    )

    assert second == {'ok': False, 'reason': 'already_used'}

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f'select * from {TEST_DATABASE}.bounty_use where team_id = %s', (team_id,))
    assert len(cursor.fetchall()) == 1
    cursor.execute(
        f"select count(*) as n from {TEST_DATABASE}.movement where team_id = %s and kind = 'adjustment'",
        (team_id,),
    )
    assert cursor.fetchone()['n'] == 1


def test_get_pending_modifier_none_until_claimed_then_set(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)

    candyland_methods.take_bounty(
        team_id, 'ADVANTAGE', 42, state['last_movement_id'], testdb=test_db
    )
    assert candyland_methods.get_pending_modifier(team_id, testdb=test_db) is None

    unclaimed = candyland_methods.get_unclaimed_bounty(team_id, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.complete_bounty(
        team_id, unclaimed['id'], 42, state['last_movement_id'], testdb=test_db
    )

    assert candyland_methods.get_pending_modifier(team_id, testdb=test_db) == 'ADVANTAGE'

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.advance_team_by_roll(
        team_id, 3, state['current_sequence'], state['current_sequence'] + 3,
        900, 42, state['last_movement_id'], testdb=test_db
    )

    assert candyland_methods.get_pending_modifier(team_id, testdb=test_db) is None


def test_get_last_bounty_since_roll_tracks_latest_then_clears(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)

    assert candyland_methods.get_last_bounty_since_roll(team_id, testdb=test_db) is None

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.take_bounty(
        team_id, 'DISADVANTAGE', 42, state['last_movement_id'], testdb=test_db
    )
    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.take_bounty(
        team_id, 'RETREAT', 42, state['last_movement_id'], testdb=test_db
    )

    assert candyland_methods.get_last_bounty_since_roll(team_id, testdb=test_db) == 'RETREAT'

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.advance_team_by_roll(
        team_id, 3, state['current_sequence'], state['current_sequence'] + 3,
        900, 42, state['last_movement_id'], testdb=test_db
    )

    assert candyland_methods.get_last_bounty_since_roll(team_id, testdb=test_db) is None


def test_replay_folds_adjustment_from_bounty(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)

    candyland_methods.record_movement(team_id, 'roll', 4, 1, 5, None, None, None, testdb=test_db)
    candyland_methods.record_movement(team_id, 'adjustment', None, 5, 4, None, None, 'bounty:RETREAT', testdb=test_db)

    state = candyland_methods.refold_team_state(team_id, testdb=test_db)

    assert state['current_sequence'] == 4


def test_move_team_forward_folds(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)

    result = candyland_methods.move_team(
        team_id, 20, 777, state['last_movement_id'], testdb=test_db
    )

    assert result['ok']
    assert result['from_sequence'] == 5 and result['to_sequence'] == 20
    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == 20
    assert state['last_movement_id'] == result['movement_id']

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        f"select * from {TEST_DATABASE}.movement where team_id = %s and kind = 'adjustment'",
        (team_id,),
    )
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]['from_sequence'] == 5 and rows[0]['to_sequence'] == 20
    assert rows[0]['roll_total'] is None


def test_move_team_backward_folds(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)

    candyland_methods.move_team(team_id, 2, 777, state['last_movement_id'], testdb=test_db)

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == 2


def test_move_team_preserves_pending_modifier(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.take_bounty(team_id, 'ADVANTAGE', 42, state['last_movement_id'], testdb=test_db)
    unclaimed = candyland_methods.get_unclaimed_bounty(team_id, testdb=test_db)
    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.complete_bounty(
        team_id, unclaimed['id'], 42, state['last_movement_id'], testdb=test_db
    )

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    candyland_methods.move_team(team_id, 15, 777, state['last_movement_id'], testdb=test_db)

    assert candyland_methods.get_pending_modifier(team_id, testdb=test_db) == 'ADVANTAGE'


def test_move_team_rejects_stale_guard(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.advance_team_by_roll(team_id, 4, 1, 5, 900, 42, None, testdb=test_db)

    stale = candyland_methods.move_team(team_id, 10, 777, None, testdb=test_db)
    assert stale == {'ok': False, 'reason': 'conflict'}

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == 5


def _seed_team_to(test_db, team_id, tile):
    candyland_methods.record_movement(
        team_id, 'adjustment', None, 1, tile, None, None, 'seed', testdb=test_db
    )
    candyland_methods.refold_team_state(team_id, testdb=test_db)
    return candyland_methods.get_team_state(team_id, testdb=test_db)


def test_set_board2_revealed_flips_once(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)

    assert candyland_methods.set_board2_revealed(event_id, testdb=test_db) is True

    first = candyland_methods.get_event('e', testdb=test_db)['board2_revealed_at']
    assert first is not None

    assert candyland_methods.set_board2_revealed(event_id, testdb=test_db) is False
    assert candyland_methods.get_event('e', testdb=test_db)['board2_revealed_at'] == first


def test_mark_board2_leader_marks_without_moving(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    other_id = candyland_methods.register_team(event_id, 'Blues', 333, 444, 1, testdb=test_db)
    state = _seed_team_to(test_db, team_id, candyland_board.BOARD1_SIZE)

    movement_id = candyland_methods.mark_board2_leader(
        team_id, 7, state['last_movement_id'], testdb=test_db
    )
    assert movement_id is not None

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f'select * from {TEST_DATABASE}.movement where id = %s', (movement_id,))
    row = cursor.fetchone()
    assert row['kind'] == 'board_transition'
    assert row['from_sequence'] == row['to_sequence'] == candyland_board.BOARD1_SIZE
    assert row['roll_total'] is None

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == candyland_board.BOARD1_SIZE
    assert candyland_methods.team_has_crossed_to_board2(team_id, testdb=test_db) is True
    assert candyland_methods.team_has_crossed_to_board2(other_id, testdb=test_db) is False


def test_mark_board2_leader_second_call_is_noop(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    state = _seed_team_to(test_db, team_id, candyland_board.BOARD1_SIZE)

    assert candyland_methods.mark_board2_leader(
        team_id, 7, state['last_movement_id'], testdb=test_db
    ) is not None

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert candyland_methods.mark_board2_leader(
        team_id, 7, state['last_movement_id'], testdb=test_db
    ) is None

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        f"select count(*) as n from {TEST_DATABASE}.movement "
        f"where team_id = %s and kind = 'board_transition'", (team_id,)
    )
    assert cursor.fetchone()['n'] == 1


def test_mark_board2_leader_rejects_stale_guard(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    _seed_team_to(test_db, team_id, candyland_board.BOARD1_SIZE)

    assert candyland_methods.mark_board2_leader(team_id, 7, None, testdb=test_db) is None

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        f"select count(*) as n from {TEST_DATABASE}.movement "
        f"where team_id = %s and kind = 'board_transition'", (team_id,)
    )
    assert cursor.fetchone()['n'] == 0


def test_teleport_team_to_board2_from_midboard(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    state = _seed_team_to(test_db, team_id, 30)

    movement_id = candyland_methods.teleport_team_to_board2(
        team_id, 7, state['last_movement_id'], testdb=test_db
    )
    assert movement_id is not None

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f'select * from {TEST_DATABASE}.movement where id = %s', (movement_id,))
    row = cursor.fetchone()
    assert row['kind'] == 'board_transition'
    assert row['from_sequence'] == 30
    assert row['to_sequence'] == candyland_board.BOARD1_SIZE + 1

    state = candyland_methods.get_team_state(team_id, testdb=test_db)
    assert state['current_sequence'] == candyland_board.BOARD1_SIZE + 1
    assert candyland_methods.team_has_crossed_to_board2(team_id, testdb=test_db) is True


def test_teleport_team_to_board2_rejects_stale_guard(test_db, setup_candyland_tables):
    event_id = candyland_methods.create_event('e', None, None, testdb=test_db)
    team_id = candyland_methods.register_team(event_id, 'Reds', 111, 222, 0, testdb=test_db)
    _seed_team_to(test_db, team_id, 30)

    assert candyland_methods.teleport_team_to_board2(team_id, 7, None, testdb=test_db) is None

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        f"select count(*) as n from {TEST_DATABASE}.movement "
        f"where team_id = %s and kind = 'board_transition'", (team_id,)
    )
    assert cursor.fetchone()['n'] == 0


def test_replay_folds_through_transition_then_roll():
    movements = [
        {'to_sequence': 40},   # roll
        {'to_sequence': 42},   # roll onto the wall
        {'to_sequence': 42},   # board_transition leader marker
        {'to_sequence': 45},   # roll off tile 42
    ]

    assert candyland_methods._replay(movements) == 45


def test_get_all_events_team_counts(test_db, setup_candyland_tables):
    event_a = candyland_methods.create_event('a', None, None, testdb=test_db)
    candyland_methods.register_team(event_a, 'Reds', 111, 222, 0, testdb=test_db)
    candyland_methods.register_team(event_a, 'Blues', 333, 444, 1, testdb=test_db)
    event_b = candyland_methods.create_event('b', None, None, testdb=test_db)

    rows = {row['slug']: row for row in candyland_methods.get_all_events(testdb=test_db)}

    assert rows['a']['team_count'] == 2
    assert rows['b']['team_count'] == 0
