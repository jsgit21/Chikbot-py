import pytest
import pymysql
from . import db_methods as database

class Author():
    def __init__(self):
        self.id = 1
        self.name = 'Joe'
        self.nick = 'Chiken'

@pytest.fixture
def test_db():
    db = database.create_connection(database='Discord_Test')
    yield db
    db.close()

@pytest.fixture
def setup_user_tables(test_db):
    cursor = test_db.cursor()

    cursor.execute('drop table if exists Discord_Test.user')
    cursor.execute('create table Discord_Test.user like Discord.user')
    cursor.execute('drop table if exists Discord_Test.user_alias')
    cursor.execute('create table Discord_Test.user_alias like Discord.user_alias')

@pytest.fixture
def test_author():
    return Author()

def test_register_user(test_db, setup_user_tables, test_author):
    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    database.register_user(test_db, test_author)

    cursor.execute('select * from Discord_Test.user where user_id = 1')
    result = cursor.fetchone()

    assert result is not None
    assert result['user_id'] == test_author.id
    assert result['username'] == test_author.name

    cursor.execute('select * from Discord_Test.user_alias where user_id = 1')
    result = cursor.fetchone()

    assert result is not None
    assert result['user_id'] == test_author.id
    assert result['alias'] == test_author.nick


