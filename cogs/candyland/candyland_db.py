import json

import pymysql

import database.db_methods as database


def create_event(slug, board_slug, starts_at, ends_at, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    query = """
        insert into candyland_event (slug, board_slug, starts_at, ends_at)
        values (%s, %s, %s, %s)
    """
    values = (
        slug,
        board_slug,
        starts_at,
        ends_at,
    )
    cursor.execute(query, values)
    return cursor.lastrowid


def get_event(slug, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, slug, board_slug, status, starts_at, ends_at, created_at
          from candyland_event
         where slug = %s
    """
    cursor.execute(query, (slug,))
    return cursor.fetchone()


def set_event_status(slug, status, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    query = """
        update candyland_event
           set status = %s
         where slug = %s
    """
    cursor.execute(query, (status, slug))


def register_team(event_id, name, role_id, forum_channel_id, sort_order, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    query = """
        insert into candyland_team
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
          from candyland_team
         where event_id = %s
           and role_id = %s
    """
    cursor.execute(query, (event_id, role_id))
    team_id = cursor.fetchone()[0]

    query = """
        select board_slug
          from candyland_event
         where id = %s
    """
    cursor.execute(query, (event_id,))
    board_slug = cursor.fetchone()[0]

    query = """
        insert ignore into candyland_team_state (team_id, board_slug, current_sequence)
        values (%s, %s, 1)
    """
    cursor.execute(query, (team_id, board_slug))

    return team_id


def get_teams(event_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, event_id, name, role_id, forum_channel_id, sort_order, created_at
          from candyland_team
         where event_id = %s
         order by sort_order
    """
    cursor.execute(query, (event_id,))
    return cursor.fetchall()


def get_team_by_role(event_id, role_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, event_id, name, role_id, forum_channel_id, sort_order, created_at
          from candyland_team
         where event_id = %s
           and role_id = %s
    """
    cursor.execute(query, (event_id, role_id))
    return cursor.fetchone()


def get_team_state(team_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select s.team_id,
               t.name,
               s.board_slug,
               s.current_sequence,
               s.last_movement_id,
               s.updated_at
          from candyland_team_state s
          join candyland_team t
            on t.id = s.team_id
         where s.team_id = %s
    """
    cursor.execute(query, (team_id,))
    return cursor.fetchone()


def get_all_state(event_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select t.id as team_id,
               t.name,
               s.board_slug,
               s.current_sequence,
               s.updated_at
          from candyland_team t
          join candyland_team_state s
            on s.team_id = t.id
         where t.event_id = %s
         order by t.sort_order
    """
    cursor.execute(query, (event_id,))
    return cursor.fetchall()


def record_movement(team_id, kind, board_slug, dice_values, from_sequence,
                    to_sequence, proof_thread_id, invoked_by_user_id, note,
                    testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    query = """
        insert into candyland_movement
            (team_id, kind, board_slug, dice_values, from_sequence, to_sequence,
             proof_thread_id, invoked_by_user_id, note)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        team_id,
        kind,
        board_slug,
        dice_values,
        from_sequence,
        to_sequence,
        proof_thread_id,
        invoked_by_user_id,
        note,
    )
    cursor.execute(query, values)
    return cursor.lastrowid


def _replay(movements):
    # Each candyland_movement row is self-describing: it records the board it
    # resolved on and the sequence it left the team at. Replaying is therefore
    # just taking the last row's board and sequence.
    board_slug = None
    sequence = 1
    for movement in movements:
        board_slug = movement['board_slug']
        sequence = movement['to_sequence']
    return board_slug, sequence


def refold_team_state(team_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, board_slug, to_sequence
          from candyland_movement
         where team_id = %s
         order by id
    """
    cursor.execute(query, (team_id,))
    movements = cursor.fetchall()

    if not movements:
        return get_team_state(team_id, testdb=testdb)

    board_slug, sequence = _replay(movements)
    last_movement_id = movements[-1]['id']

    query = """
        insert into candyland_team_state
            (team_id, board_slug, current_sequence, last_movement_id)
        values (%s, %s, %s, %s)
        on duplicate key update
            board_slug = values(board_slug),
            current_sequence = values(current_sequence),
            last_movement_id = values(last_movement_id)
    """
    cursor.execute(query, (team_id, board_slug, sequence, last_movement_id))

    return get_team_state(team_id, testdb=testdb)


def claim_team_for_roll(team_id, expected_movement_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    # pymysql reports rows changed, not rows matched, so the conditional
    # no-op UPDATE this guard would normally use always reports 0. Count the
    # matching row instead: 1 means last_movement_id is still what Phase B
    # expects, 0 means someone else moved the team first.
    query = """
        select count(*)
          from candyland_team_state
         where team_id = %s
           and last_movement_id <=> %s
    """
    cursor.execute(query, (team_id, expected_movement_id))
    return cursor.fetchone()[0]


def open_tile_thread(team_id, board_slug, tile_sequence, thread_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    query = """
        insert into candyland_tile_thread
            (team_id, board_slug, tile_sequence, thread_id)
        values (%s, %s, %s, %s)
    """
    cursor.execute(query, (team_id, board_slug, tile_sequence, thread_id))
    return cursor.lastrowid


def get_open_thread(team_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, team_id, board_slug, tile_sequence, thread_id, state,
               opened_at, closed_at
          from candyland_tile_thread
         where team_id = %s
           and state = 'open'
    """
    cursor.execute(query, (team_id,))
    return cursor.fetchone()


def close_tile_thread(thread_row_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    query = """
        update candyland_tile_thread
           set state = 'closed',
               closed_at = now()
         where id = %s
    """
    cursor.execute(query, (thread_row_id,))


def record_bounty_use(team_id, board_slug, bounty_key, used_on_sequence,
                      movement_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    query = """
        insert into candyland_bounty_use
            (team_id, board_slug, bounty_key, used_on_sequence, movement_id)
        values (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (team_id, board_slug, bounty_key, used_on_sequence, movement_id))


def get_bounty_uses(team_id, board_slug, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, team_id, board_slug, bounty_key, used_on_sequence, movement_id,
               created_at
          from candyland_bounty_use
         where team_id = %s
           and board_slug = %s
    """
    cursor.execute(query, (team_id, board_slug))
    return cursor.fetchall()


def write_audit(actor_user_id, action, payload_dict, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    query = """
        insert into candyland_audit (actor_user_id, action, payload)
        values (%s, %s, %s)
    """
    cursor.execute(query, (actor_user_id, action, json.dumps(payload_dict)))
