import pytest
import pymysql
from database import db_methods
from cogs.candyland import candyland_db_methods as candyland_methods

TEST_DATABASE = 'candyland_test'
SOURCE_DATABASE = 'candyland'

# Child-before-parent for drops, parent-before-child for creates.
TABLES = [
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
