import pytest
import pymysql
from database import db_methods
from cogs.candyland import candyland_db

TEST_DATABASE = 'Discord_Test'

# Child-before-parent for drops, parent-before-child for creates.
CANDYLAND_TABLES = [
    'candyland_movement',
    'candyland_team_state',
    'candyland_team',
    'candyland_event',
]


@pytest.fixture(scope='module')
def test_db():
    db = db_methods.create_connection(database=TEST_DATABASE)
    yield db
    db.close()


@pytest.fixture
def setup_candyland_tables(test_db):
    cursor = test_db.cursor()

    for table in CANDYLAND_TABLES:
        cursor.execute(f'drop table if exists {TEST_DATABASE}.{table}')
    for table in reversed(CANDYLAND_TABLES):
        cursor.execute(f'create table {TEST_DATABASE}.{table} like Discord.{table}')


def test_create_and_get_event(test_db, setup_candyland_tables):
    event_id = candyland_db.create_event('cgl-2026', 'standard', None, None, testdb=test_db)
    event = candyland_db.get_event('cgl-2026', testdb=test_db)

    assert event['id'] == event_id
    assert event['slug'] == 'cgl-2026'
    assert event['board_slug'] == 'standard'
    assert event['status'] == 'setup'


def test_register_team_is_idempotent(test_db, setup_candyland_tables):
    event_id = candyland_db.create_event('cgl-2026', 'standard', None, None, testdb=test_db)

    first = candyland_db.register_team(event_id, 'Team 1', 111, 222, 0, testdb=test_db)
    second = candyland_db.register_team(event_id, 'Team 1 renamed', 111, 999, 0, testdb=test_db)

    assert first == second

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f'select * from {TEST_DATABASE}.candyland_team where event_id = %s', (event_id,))
    teams = cursor.fetchall()

    assert len(teams) == 1
    assert teams[0]['name'] == 'Team 1 renamed'
    assert teams[0]['forum_channel_id'] == 999

    cursor.execute(
        f'select count(*) as n from {TEST_DATABASE}.candyland_team_state where team_id = %s',
        (first,),
    )
    assert cursor.fetchone()['n'] == 1


def test_replay_folds_to_last_movement():
    movements = [
        {'board_slug': 'standard', 'to_sequence': 4},
        {'board_slug': 'standard', 'to_sequence': 3},   # adjustment
        {'board_slug': 'hard', 'to_sequence': 1},       # board_transition
    ]

    assert candyland_db._replay(movements) == ('hard', 1)


def test_refold_team_state_writes_fold(test_db, setup_candyland_tables):
    event_id = candyland_db.create_event('cgl-2026', 'standard', None, None, testdb=test_db)
    team_id = candyland_db.register_team(event_id, 'Team 1', 111, 222, 0, testdb=test_db)

    candyland_db.record_movement(team_id, 'roll', 'standard', '3', 1, 4, None, None, None, testdb=test_db)
    candyland_db.record_movement(team_id, 'adjustment', 'standard', None, 4, 3, None, None, 'fix', testdb=test_db)
    last_id = candyland_db.record_movement(team_id, 'board_transition', 'hard', None, 3, 1, None, None, None, testdb=test_db)

    state = candyland_db.refold_team_state(team_id, testdb=test_db)

    assert state['board_slug'] == 'hard'
    assert state['current_sequence'] == 1
    assert state['last_movement_id'] == last_id


def test_claim_team_for_roll_guards_on_last_movement(test_db, setup_candyland_tables):
    event_id = candyland_db.create_event('cgl-2026', 'standard', None, None, testdb=test_db)
    team_id = candyland_db.register_team(event_id, 'Team 1', 111, 222, 0, testdb=test_db)

    movement_id = candyland_db.record_movement(team_id, 'roll', 'standard', '2', 1, 3, None, None, None, testdb=test_db)
    candyland_db.refold_team_state(team_id, testdb=test_db)

    assert candyland_db.claim_team_for_roll(team_id, movement_id, testdb=test_db) == 1
    assert candyland_db.claim_team_for_roll(team_id, movement_id + 999, testdb=test_db) == 0


def test_get_all_state_one_row_per_team_in_sort_order(test_db, setup_candyland_tables):
    event_id = candyland_db.create_event('cgl-2026', 'standard', None, None, testdb=test_db)
    candyland_db.register_team(event_id, 'Bravo', 20, 21, 1, testdb=test_db)
    candyland_db.register_team(event_id, 'Alpha', 10, 11, 0, testdb=test_db)
    candyland_db.register_team(event_id, 'Charlie', 30, 31, 2, testdb=test_db)

    rows = candyland_db.get_all_state(event_id, testdb=test_db)

    assert [r['name'] for r in rows] == ['Alpha', 'Bravo', 'Charlie']
    assert all(r['current_sequence'] == 1 for r in rows)
