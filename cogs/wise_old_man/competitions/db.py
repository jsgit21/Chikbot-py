import pymysql
import database.db_methods as database


def ensure_competition_row(competition_id, cycle_id=None, verification_code=None,
                           nominator_user_id=None, kickoff_status=None, testdb=None):
    """Insert a competition row if one doesn't already exist for this id.

    Used both for a stray competition found by detection (bare row, no
    cycle_id/verification_code/nominator_user_id) and for a row created via
    /competition create or create-otw (all set at once). A no-op if the row exists.
    kickoff_status is only ever set for a standalone (solo) competition -- paired
    competitions track this via competition_cycle.status instead, so it stays null
    for them.
    """
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute(
        """
        insert into competition (competition_id, cycle_id, verification_code, nominator_user_id, kickoff_status)
             values (%s, %s, %s, %s, %s)
        on duplicate key update competition_id = competition_id
        """,
        (competition_id, cycle_id, verification_code, nominator_user_id, kickoff_status),
    )


def get_competition_by_id(competition_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute('select * from competition where competition_id = %s', (competition_id,))
    return cursor.fetchone()


def set_results_status(competition_id, status, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute(
        'update competition set results_status = %s where competition_id = %s',
        (status, competition_id),
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


def claim_competition_for_announcing(competition_id, testdb=None):
    """Atomically move a competition from 'drafted' to 'announcing'. Returns rowcount (0 if already claimed)."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute(
        "update competition set results_status = 'announcing' "
        "where competition_id = %s and results_status = 'drafted'", (competition_id,))
    return cursor.rowcount


def get_unprocessed_competitions(testdb=None):
    """Return competition rows winner detection hasn't drafted results for yet."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute("select * from competition where results_status = 'pending'")
    return cursor.fetchall()


def get_drafted_competitions(testdb=None):
    """Return competition rows with a results draft awaiting mod approval."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute("select * from competition where results_status = 'drafted'")
    return cursor.fetchall()


def get_competitions_awaiting_kickoff(testdb=None):
    """Return solo competition rows whose kickoff announcement hasn't been approved yet."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute("select * from competition where kickoff_status = 'drafted'")
    return cursor.fetchall()


def set_kickoff_status(competition_id, status, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute(
        'update competition set kickoff_status = %s where competition_id = %s',
        (status, competition_id),
    )


def claim_cycle_for_publishing(cycle_id, testdb=None):
    """Atomically move a cycle from 'planned' to 'publishing'. Returns rowcount (0 if already claimed)."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute(
        "update competition_cycle set status = 'publishing' "
        "where id = %s and status = 'planned'", (cycle_id,))
    return cursor.rowcount


def get_planned_cycles(testdb=None):
    """Return cycles created by /competition create but not yet kicked off."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        "select * from competition_cycle where status = 'planned' order by starts_at desc"
    )
    return cursor.fetchall()


def get_active_cycles(testdb=None):
    """Return cycles currently running (kicked off, not yet ended)."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        "select * from competition_cycle where status = 'active' order by ends_at desc"
    )
    return cursor.fetchall()


def get_planned_cycle_for_window(starts_at, ends_at, testdb=None):
    """Return the 'planned' cycle for an exact starts_at/ends_at window, or None.

    Lets /competition create detect a cycle stuck mid-creation (e.g. BOTW POSTed
    to WOM but SOTW failed) and resume it instead of duplicating the BOTW side.
    """
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        "select * from competition_cycle where status = 'planned' and starts_at = %s and ends_at = %s",
        (starts_at, ends_at),
    )
    return cursor.fetchone()


def get_last_cycle(testdb=None):
    """Return the most recently ended cycle (any status), or None if there isn't one."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        'select * from competition_cycle order by ends_at desc limit 1'
    )
    return cursor.fetchone()


def get_competitions_for_cycle(cycle_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute('select * from competition where cycle_id = %s', (cycle_id,))
    return cursor.fetchall()


def get_any_group_rsn(testdb=None):
    """Return one current RSN from wom_group, or None if the group is empty."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute('select rsn from wom_group limit 1')
    row = cursor.fetchone()
    return row[0] if row else None


def get_rsn_for_wom_id(wom_user_id, testdb=None):
    """Return the current RSN from wom_group for a WOM player id, or None."""
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()
    cursor.execute('select rsn from wom_group where wom_user_id = %s', (wom_user_id,))
    row = cursor.fetchone()
    return row[0] if row else None
