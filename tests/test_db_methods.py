import time
import pytest
import pymysql
from database import db_methods
from cogs.user_goals import goal_db_methods as goal_methods

TEST_DATABASE = 'Discord_Test'


class Author():
    def __init__(self, id=1, name='Joe', nick='Chiken'):
        self.id = id
        self.name = name
        self.nick = nick


@pytest.fixture(scope='module')
def test_db():
    db = db_methods.create_connection(database=TEST_DATABASE)
    yield db
    db.close()


@pytest.fixture
def setup_user_tables(test_db):
    cursor = test_db.cursor()

    for table in ['user', 'user_alias']:
        cursor.execute(f'drop table if exists {TEST_DATABASE}.{table}')
        cursor.execute(f'create table {TEST_DATABASE}.{table} like Discord.{table}')


@pytest.fixture
def test_author():
    return Author()


def test_register_user(test_db, setup_user_tables, test_author):
    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    db_methods.register_user(test_author, testdb=test_db)

    cursor.execute(f'select * from {TEST_DATABASE}.user where user_id = 1')
    result = cursor.fetchone()

    assert result is not None
    assert result['user_id'] == test_author.id
    assert result['username'] == test_author.name

    cursor.execute(f'select * from {TEST_DATABASE}.user_alias where user_id = 1')
    result = cursor.fetchone()

    assert result is not None
    assert result['user_id'] == test_author.id
    assert result['alias'] == test_author.nick


# Module scope means it should only run once
@pytest.fixture(scope='module')
def setup_goal_tables(test_db):
    cursor = test_db.cursor()
    author = Author()

    def add_sub_goals(num_goals):
        for i in range(1, num_goals):
            goal = f'{i}'
            goal_methods.add_goal(author.id, goal, num_goals, testdb=test_db)

    # I use the create table statement here so that I can capture the 
    # ON DELETE CASCADE property
    cursor.execute(f'drop table if exists {TEST_DATABASE}.user_goal')
    cursor.execute(f'show create table Discord.user_goal')
    result = cursor.fetchone()
    user_goal = result[1].split('ENGINE')[0]
    cursor.execute(user_goal)

    cursor.execute(f'drop view if exists {TEST_DATABASE}.ordered_goals')
    cursor.execute(f'show create view Discord.ordered_goals')
    result = cursor.fetchone()
    view_sql = result[1].replace('Discord',TEST_DATABASE)
    cursor.execute(view_sql)

    for i in range(1, 6):
        goal = f'{i}'
        goal_methods.add_goal(author.id, goal, parent_goal_number=None, testdb=test_db)

    # Separate loop because I want subgoals to be at the bottom of user_goals
    for i in range(1, 6):
        add_sub_goals(i)

    # For each row's timestamp, add ID number of seconds
    # This is required because when programatically adding records the
    # timestamps are the same. This will never happen when a user adds goals
    # And equal timestamps creates an issue with ordering
    fix_timestamps = f"""
        update {TEST_DATABASE}.user_goal
           set insert_date = date_add(insert_date, interval id second)
    """
    cursor.execute(fix_timestamps)


def test_goals_order(test_db, setup_goal_tables):
    cursor = test_db.cursor(pymysql.cursors.DictCursor)

    cursor.execute(f'select * from {TEST_DATABASE}.ordered_goals where not sub_goal')
    results = cursor.fetchall()

    for row in results:
        assert row['id'] == int(row['goal']) == row['rnk']


def test_sub_goals_order(test_db, setup_goal_tables):
    """
        This tests that the view ordering is working correctly with subgoals
    """
    cursor = test_db.cursor(pymysql.cursors.DictCursor)

    cursor.execute(f'select * from {TEST_DATABASE}.ordered_goals where sub_goal')
    results = cursor.fetchall()

    for r in results:
        parent_id = r['parent_id']
        rank = r['rnk']

        if parent_id == 2:
            assert rank in [3]
        elif parent_id == 3:
            assert rank in [5, 6]
        elif parent_id == 4:
            assert rank in [8, 9, 10]
        elif parent_id == 5:
            assert rank in [12, 13, 14, 15]


@pytest.fixture()
def delete_goal(test_db, goal_id):
    cursor = test_db.cursor(pymysql.cursors.DictCursor)

    # Create a temp table to move the table the record between
    # Instead of deleting it, so we restore the record exactly
    cursor.execute(f'drop table if exists {TEST_DATABASE}.tmp_goal')
    query = f"""
        create table {TEST_DATABASE}.tmp_goal
        select *
          from {TEST_DATABASE}.user_goal
         where id = {goal_id}
            or parent_id = {goal_id}
    """
    cursor.execute(query)
    cursor.execute(f'delete from {TEST_DATABASE}.user_goal where id = {goal_id}')

    yield

    query = f"""
        insert into {TEST_DATABASE}.user_goal
        select *
          from {TEST_DATABASE}.tmp_goal
    """
    cursor.execute(query)
    cursor.execute(f'drop table if exists {TEST_DATABASE}.tmp_goal')


# This decorator will call test_delete_sub_goal for all of our parameters,
# injecting each parameter into goal_id, which also injects it into delete_goal
@pytest.mark.parametrize('goal_id', [10])
def test_delete_sub_goal(test_db, setup_goal_tables, delete_goal, goal_id):
    """
        This test deletes the second sub goal for a main goal that has three sub goals
        It's expected that the third sub goal will shift rank up
        Rank: 8, 9, 10
            > Delete rank 9
        Rank: 8, 9
    """
    cursor = test_db.cursor(pymysql.cursors.DictCursor)

    cursor.execute(f'select * from {TEST_DATABASE}.ordered_goals where parent_id = 4')
    results = cursor.fetchall()

    for r in results:
        rank = r['rnk']
        assert rank in [8, 9]


@pytest.mark.parametrize('goal_id', [5])
def test_delete_main_goal(test_db, setup_goal_tables, delete_goal, goal_id):
    """
        This test deletes a main goal that has sub goals
        It's expected that the ON DELETE CASCADE will delete any sub goals when
        the parent goal is deleted
    """
    cursor = test_db.cursor()

    cursor.execute(f'select count(*) from {TEST_DATABASE}.ordered_goals where parent_id = 5')
    count = cursor.fetchone()[0]

    assert count == 0
