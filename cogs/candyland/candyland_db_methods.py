import json

import pymysql

from . import candyland_connection as connection


def create_event(slug, starts_at, ends_at, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        insert into event (slug, starts_at, ends_at)
        values (%s, %s, %s)
    """
    values = (
        slug,
        starts_at,
        ends_at,
    )
    cursor.execute(query, values)
    return cursor.lastrowid


def get_event(slug, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, slug, status, starts_at, ends_at, created_at
          from event
         where slug = %s
    """
    cursor.execute(query, (slug,))
    return cursor.fetchone()


def get_active_event(testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, slug, status, starts_at, ends_at, created_at
          from event
         where status = 'live'
         order by id desc
         limit 1
    """
    cursor.execute(query)
    return cursor.fetchone()


def set_event_status(slug, status, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        update event
           set status = %s
         where slug = %s
    """
    cursor.execute(query, (status, slug))


def register_team(event_id, name, role_id, forum_channel_id, sort_order, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        insert into team
            (event_id, name, role_id, forum_channel_id, sort_order)
        values (%s, %s, %s, %s, %s)
        on duplicate key update
            name = values(name),
            forum_channel_id = values(forum_channel_id)
    """
    values = (
        event_id,
        name,
        role_id,
        forum_channel_id,
        sort_order,
    )
    cursor.execute(query, values)

    query = """
        select id
          from team
         where event_id = %s
           and role_id = %s
    """
    cursor.execute(query, (event_id, role_id))
    team_id = cursor.fetchone()[0]

    query = """
        insert ignore into team_state (team_id, current_sequence)
        values (%s, 1)
    """
    cursor.execute(query, (team_id,))

    return team_id


def get_teams(event_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, event_id, name, role_id, forum_channel_id, sort_order, created_at
          from team
         where event_id = %s
         order by sort_order
    """
    cursor.execute(query, (event_id,))
    return cursor.fetchall()


def get_team_by_role(event_id, role_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, event_id, name, role_id, forum_channel_id, sort_order, created_at
          from team
         where event_id = %s
           and role_id = %s
    """
    cursor.execute(query, (event_id, role_id))
    return cursor.fetchone()


def get_team_state(team_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select s.team_id,
               t.name,
               s.current_sequence,
               s.last_movement_id,
               s.updated_at
          from team_state s
          join team t
            on t.id = s.team_id
         where s.team_id = %s
    """
    cursor.execute(query, (team_id,))
    return cursor.fetchone()


def get_all_state(event_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select t.id as team_id,
               t.name,
               s.current_sequence,
               s.updated_at
          from team t
          join team_state s
            on s.team_id = t.id
         where t.event_id = %s
         order by t.sort_order
    """
    cursor.execute(query, (event_id,))
    return cursor.fetchall()


def record_movement(team_id, kind, roll_total, from_sequence,
                    to_sequence, proof_thread_id, invoked_by_user_id, note,
                    testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        insert into movement
            (team_id, kind, roll_total, from_sequence, to_sequence,
             proof_thread_id, invoked_by_user_id, note)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        team_id,
        kind,
        roll_total,
        from_sequence,
        to_sequence,
        proof_thread_id,
        invoked_by_user_id,
        note,
    )
    cursor.execute(query, values)
    return cursor.lastrowid


def _replay(movements):
    # Each movement row records the sequence it left the team at. Replaying
    # is just taking the last row's to_sequence.
    sequence = 1
    for movement in movements:
        sequence = movement['to_sequence']
    return sequence


def refold_team_state(team_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, to_sequence
          from movement
         where team_id = %s
         order by id
    """
    cursor.execute(query, (team_id,))
    movements = cursor.fetchall()

    if not movements:
        return get_team_state(team_id, testdb=testdb)

    sequence = _replay(movements)
    last_movement_id = movements[-1]['id']

    query = """
        insert into team_state
            (team_id, current_sequence, last_movement_id)
        values (%s, %s, %s)
        on duplicate key update
            current_sequence = values(current_sequence),
            last_movement_id = values(last_movement_id)
    """
    cursor.execute(query, (team_id, sequence, last_movement_id))

    return get_team_state(team_id, testdb=testdb)


def advance_team_by_roll(team_id, roll_total, from_sequence,
                         to_sequence, proof_thread_id, invoked_by_user_id,
                         expected_movement_id, testdb=None):
    # The one place in the codebase that needs a real transaction: two team
    # members spamming /candyland roll in the same second must not both advance
    # the team. SELECT ... FOR UPDATE on the team_state row serialises them; the
    # loser sees a changed last_movement_id and is turned away with None.
    db = testdb if testdb else connection.create_connection()
    db.begin()
    try:
        cursor = db.cursor()
        cursor.execute(
            """
            select last_movement_id, current_sequence
              from team_state
             where team_id = %s
             for update
            """,
            (team_id,),
        )
        locked = cursor.fetchone()
        if locked is None:
            db.rollback()
            return None

        locked_movement_id, locked_sequence = locked
        if locked_movement_id != expected_movement_id or locked_sequence != from_sequence:
            db.rollback()
            return None

        movement_id = record_movement(
            team_id, 'roll', roll_total, from_sequence, to_sequence,
            proof_thread_id, invoked_by_user_id, None, testdb=db,
        )
        refold_team_state(team_id, testdb=db)
        db.commit()
        return movement_id
    except Exception:
        db.rollback()
        raise


def open_tile_thread(team_id, tile_sequence, thread_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        insert into tile_thread
            (team_id, tile_sequence, thread_id)
        values (%s, %s, %s)
    """
    cursor.execute(query, (team_id, tile_sequence, thread_id))
    return cursor.lastrowid


def get_any_thread(team_id, testdb=None):
    # Most recent tile_thread row for the team regardless of state. /candyland
    # start uses this for idempotency: a team that already has any thread row
    # has been kicked off, so re-running start must not open a second tile-1
    # thread (which would also collide on the (team_id, tile_sequence) key).
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, team_id, tile_sequence, thread_id, state,
               opened_at, closed_at
          from tile_thread
         where team_id = %s
         order by id desc
         limit 1
    """
    cursor.execute(query, (team_id,))
    return cursor.fetchone()


def get_open_thread(team_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, team_id, tile_sequence, thread_id, state,
               opened_at, closed_at
          from tile_thread
         where team_id = %s
           and state = 'open'
    """
    cursor.execute(query, (team_id,))
    return cursor.fetchone()


def close_tile_thread(thread_row_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        update tile_thread
           set state = 'closed',
               closed_at = now()
         where id = %s
    """
    cursor.execute(query, (thread_row_id,))


def swap_open_thread(team_id, tile_sequence, new_thread_id, old_thread_row_id,
                     testdb=None):
    # Open the next tile's thread row and close the previous one as a single
    # transaction: a failure between the two must not leave a team with two
    # state='open' rows (get_open_thread does fetchone() and would pick one
    # arbitrarily, breaking the one-open-thread-per-team invariant).
    db = testdb if testdb else connection.create_connection()
    db.begin()
    try:
        open_tile_thread(team_id, tile_sequence, new_thread_id, testdb=db)
        close_tile_thread(old_thread_row_id, testdb=db)
        db.commit()
    except Exception:
        db.rollback()
        raise


def clear_event_play_data(event_id, testdb=None):
    # Test-only reset: wipe every play-generated row for the event's teams and
    # send the event back to 'setup' so /candyland start can run again. Keeps the
    # event and its teams. Never call this on a real event.
    db = testdb if testdb else connection.create_connection()
    db.begin()
    try:
        cursor = db.cursor()
        for stmt in (
            "delete bu from bounty_use bu join team t on t.id = bu.team_id where t.event_id = %s",
            "delete m from movement m join team t on t.id = m.team_id where t.event_id = %s",
            "delete tt from tile_thread tt join team t on t.id = tt.team_id where t.event_id = %s",
            "update team_state s join team t on t.id = s.team_id "
            "   set s.current_sequence = 1, s.last_movement_id = null where t.event_id = %s",
            "update event set status = 'setup' where id = %s",
        ):
            cursor.execute(stmt, (event_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise


def record_bounty_use(team_id, board_number, bounty_key, used_on_sequence,
                      movement_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        insert into bounty_use
            (team_id, board_number, bounty_key, used_on_sequence, movement_id)
        values (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (team_id, board_number, bounty_key, used_on_sequence, movement_id))


def get_bounty_uses(team_id, board_number, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, team_id, board_number, bounty_key, used_on_sequence, movement_id,
               created_at
          from bounty_use
         where team_id = %s
           and board_number = %s
    """
    cursor.execute(query, (team_id, board_number))
    return cursor.fetchall()


def write_audit(actor_user_id, action, payload_dict, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        insert into audit (actor_user_id, action, payload)
        values (%s, %s, %s)
    """
    cursor.execute(query, (actor_user_id, action, json.dumps(payload_dict)))
