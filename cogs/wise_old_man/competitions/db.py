import pymysql

import database.db_methods as database


def upsert_competition(comp_id, cycle_id, comp_type, metric, title,
                       starts_at, ends_at, verification_code=None,
                       picker_user_id=None, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    query = """
        insert into competition
               (competition_id, cycle_id, type, metric, title, starts_at, ends_at,
                verification_code, picker_user_id)
             values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        on duplicate key update
               cycle_id           = coalesce(values(cycle_id), cycle_id),
               metric             = values(metric),
               title              = values(title),
               starts_at          = values(starts_at),
               ends_at            = values(ends_at),
               verification_code  = coalesce(values(verification_code), verification_code),
               picker_user_id     = coalesce(values(picker_user_id), picker_user_id)
    """
    cursor.execute(query, (
        comp_id, cycle_id, comp_type, metric, title,
        starts_at, ends_at, verification_code, picker_user_id,
    ))


def get_competition_by_id(competition_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute('select * from competition where competition_id = %s', (competition_id,))
    return cursor.fetchone()


def set_competition_winner(competition_id, winner_wom_user_id, winner_gained, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute(
        'update competition set winner_wom_user_id = %s, winner_gained = %s where competition_id = %s',
        (winner_wom_user_id, winner_gained, competition_id),
    )


def mark_results_posted(competition_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute(
        'update competition set results_posted = true where competition_id = %s',
        (competition_id,),
    )


def insert_cycle(starts_at, ends_at, status='planned', testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute(
        'insert into competition_cycle (starts_at, ends_at, status) values (%s, %s, %s)',
        (starts_at, ends_at, status),
    )
    return cursor.lastrowid


def set_cycle_status(cycle_id, status, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute(
        'update competition_cycle set status = %s where id = %s',
        (status, cycle_id),
    )


def get_pending_cycles(testdb=None):
    """Return cycles that have ended but not yet been announced."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        "select * from competition_cycle where status = 'ended' order by ends_at desc"
    )
    return cursor.fetchall()


def get_competitions_for_cycle(cycle_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute('select * from competition where cycle_id = %s', (cycle_id,))
    return cursor.fetchall()


def get_rsn_for_wom_id(wom_user_id, testdb=None):
    """Return the current RSN from wom_group for a WOM player id, or None."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute('select rsn from wom_group where wom_user_id = %s', (wom_user_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def get_wom_id_for_rsn(rsn, testdb=None):
    """Return the wom_user_id from wom_group for an RSN (lowercased), or None."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute('select wom_user_id from wom_group where rsn = %s', (rsn.lower(),))
    row = cursor.fetchone()
    return row[0] if row else None
