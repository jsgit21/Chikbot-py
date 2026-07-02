import pytest
import pymysql

from database import db_methods
from cogs.wise_old_man.identity import db as identity_db

TEST_DATABASE = 'Discord_Test'


@pytest.fixture(scope='module')
def test_db():
    db = db_methods.create_connection(database=TEST_DATABASE)
    yield db
    db.close()


@pytest.fixture
def setup_identity_tables(test_db):
    cursor = test_db.cursor()

    # Drop child first; clones use CREATE TABLE LIKE which omits foreign keys.
    for table in ['wom_link', 'wom_group', 'user']:
        cursor.execute(f'drop table if exists {TEST_DATABASE}.{table}')
    for table in ['user', 'wom_group', 'wom_link']:
        cursor.execute(f'create table {TEST_DATABASE}.{table} like Discord.{table}')

    cursor.executemany(
        f'insert into {TEST_DATABASE}.user (user_id, username) values (%s, %s)',
        [(1, 'joe'), (2, 'nick')],
    )
    cursor.executemany(
        f'insert into {TEST_DATABASE}.wom_group (wom_user_id, rsn, `rank`) values (%s, %s, %s)',
        [(100, 'spoiled mayo', 'ruby'), (101, 'peppy x', 'diamond'), (102, 'sinistercrab', 'onyx')],
    )


def _linked_user_id(test_db, wom_user_id):
    cursor = test_db.cursor()
    cursor.execute(f'select user_id from {TEST_DATABASE}.wom_link where wom_user_id = %s', (wom_user_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def _rename(test_db, wom_user_id, new_rsn):
    # Simulate what the daily wom_group sync does on an in-game rename.
    cursor = test_db.cursor()
    cursor.execute(
        f'update {TEST_DATABASE}.wom_group set rsn = %s where wom_user_id = %s',
        (new_rsn, wom_user_id),
    )


def test_link_rsn(test_db, setup_identity_tables):
    match = identity_db.link_rsn('spoiled mayo', 1, testdb=test_db)

    assert match is not None
    assert match['wom_user_id'] == 100
    assert _linked_user_id(test_db, 100) == 1


def test_link_rsn_normalizes_hyphen_and_case(test_db, setup_identity_tables):
    match = identity_db.link_rsn('Spoiled-Mayo', 1, testdb=test_db)

    assert match is not None
    assert match['rsn'] == 'spoiled mayo'


def test_link_rsn_not_in_group(test_db, setup_identity_tables):
    assert identity_db.link_rsn('nonexistent', 1, testdb=test_db) is None


def test_link_rsn_relink_updates_user(test_db, setup_identity_tables):
    identity_db.link_rsn('spoiled mayo', 1, testdb=test_db)
    identity_db.link_rsn('spoiled mayo', 2, testdb=test_db)

    assert _linked_user_id(test_db, 100) == 2


def test_unlink_rsn(test_db, setup_identity_tables):
    identity_db.link_rsn('spoiled mayo', 1, testdb=test_db)
    removed = identity_db.unlink_rsn('spoiled mayo', testdb=test_db)

    assert removed == 1
    assert _linked_user_id(test_db, 100) is None


def test_set_preferred_alias(test_db, setup_identity_tables):
    identity_db.set_preferred_alias(1, 'mayo', testdb=test_db)

    cursor = test_db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f'select preferred_alias from {TEST_DATABASE}.user where user_id = 1')
    assert cursor.fetchone()['preferred_alias'] == 'mayo'


def test_get_unlinked_members(test_db, setup_identity_tables):
    identity_db.link_rsn('spoiled mayo', 1, testdb=test_db)
    unlinked = identity_db.get_unlinked_members(testdb=test_db)

    names = {m['rsn'] for m in unlinked}
    assert names == {'peppy x', 'sinistercrab'}


def test_whois_rsn(test_db, setup_identity_tables):
    identity_db.link_rsn('peppy x', 2, testdb=test_db)
    identity_db.set_preferred_alias(2, 'peppy', testdb=test_db)

    row = identity_db.whois_rsn('peppy x', testdb=test_db)
    assert row['user_id'] == 2
    assert row['preferred_alias'] == 'peppy'


def test_whois_user_returns_all_rsns(test_db, setup_identity_tables):
    identity_db.link_rsn('spoiled mayo', 1, testdb=test_db)
    # Re-point a second RSN at the same Discord user (one-to-many).
    identity_db.link_rsn('peppy x', 1, testdb=test_db)

    rows = identity_db.whois_user(1, testdb=test_db)
    assert {r['rsn'] for r in rows} == {'spoiled mayo', 'peppy x'}


def test_discord_user_for_rsn(test_db, setup_identity_tables):
    identity_db.link_rsn('sinistercrab', 2, testdb=test_db)

    row = identity_db.discord_user_for_rsn('sinistercrab', testdb=test_db)
    assert row['user_id'] == 2


def test_discord_user_for_rsn_unlinked(test_db, setup_identity_tables):
    assert identity_db.discord_user_for_rsn('sinistercrab', testdb=test_db) is None


def test_discord_user_for_wom_id(test_db, setup_identity_tables):
    identity_db.link_rsn('sinistercrab', 2, testdb=test_db)

    row = identity_db.discord_user_for_wom_id(102, testdb=test_db)
    assert row['user_id'] == 2


def test_link_survives_rename(test_db, setup_identity_tables):
    # Link under the old name, then the daily sync renames the account.
    identity_db.link_rsn('spoiled mayo', 1, testdb=test_db)
    _rename(test_db, 100, 'fresh mayo')

    # New name resolves; old name no longer does; stable id always resolves.
    assert identity_db.discord_user_for_rsn('fresh mayo', testdb=test_db)['user_id'] == 1
    assert identity_db.discord_user_for_rsn('spoiled mayo', testdb=test_db) is None
    assert identity_db.discord_user_for_wom_id(100, testdb=test_db)['user_id'] == 1
    assert identity_db.whois_user(1, testdb=test_db)[0]['rsn'] == 'fresh mayo'


# ---------------------------------------------------------------------------
# claim_rsn
# ---------------------------------------------------------------------------

def test_claim_rsn_success(test_db, setup_identity_tables):
    status, member = identity_db.claim_rsn('spoiled mayo', 1, testdb=test_db)

    assert status == 'linked'
    assert member['wom_user_id'] == 100
    assert _linked_user_id(test_db, 100) == 1


def test_claim_rsn_already_yours(test_db, setup_identity_tables):
    identity_db.claim_rsn('spoiled mayo', 1, testdb=test_db)
    status, member = identity_db.claim_rsn('spoiled mayo', 1, testdb=test_db)

    assert status == 'already_yours'
    assert member['wom_user_id'] == 100


def test_claim_rsn_already_claimed_by_other(test_db, setup_identity_tables):
    identity_db.claim_rsn('spoiled mayo', 1, testdb=test_db)
    status, member = identity_db.claim_rsn('spoiled mayo', 2, testdb=test_db)

    assert status == 'already_claimed'
    assert _linked_user_id(test_db, 100) == 1  # original owner unchanged


def test_claim_rsn_not_in_group(test_db, setup_identity_tables):
    status, member = identity_db.claim_rsn('nobody', 1, testdb=test_db)

    assert status == 'not_in_group'
    assert member is None


def test_claim_rsn_normalizes_input(test_db, setup_identity_tables):
    status, member = identity_db.claim_rsn('Spoiled-Mayo', 1, testdb=test_db)

    assert status == 'linked'
    assert member['rsn'] == 'spoiled mayo'


# ---------------------------------------------------------------------------
# unclaim_rsn
# ---------------------------------------------------------------------------

def test_unclaim_rsn_success(test_db, setup_identity_tables):
    identity_db.claim_rsn('spoiled mayo', 1, testdb=test_db)
    status = identity_db.unclaim_rsn('spoiled mayo', 1, testdb=test_db)

    assert status == 'unlinked'
    assert _linked_user_id(test_db, 100) is None


def test_unclaim_rsn_not_yours(test_db, setup_identity_tables):
    identity_db.claim_rsn('spoiled mayo', 1, testdb=test_db)
    status = identity_db.unclaim_rsn('spoiled mayo', 2, testdb=test_db)

    assert status == 'not_yours'
    assert _linked_user_id(test_db, 100) == 1  # link untouched


def test_unclaim_rsn_not_linked(test_db, setup_identity_tables):
    status = identity_db.unclaim_rsn('spoiled mayo', 1, testdb=test_db)

    assert status == 'not_linked'


def test_unclaim_rsn_not_in_group(test_db, setup_identity_tables):
    status = identity_db.unclaim_rsn('nobody', 1, testdb=test_db)

    assert status == 'not_in_group'
