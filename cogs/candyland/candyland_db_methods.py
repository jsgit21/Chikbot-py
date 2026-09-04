import json

import pymysql

from . import candyland_board, candyland_bounty
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
        select id, slug, status, board2_revealed_at, starts_at, ends_at, created_at
          from event
         where slug = %s
    """
    cursor.execute(query, (slug,))
    return cursor.fetchone()


def get_active_event(testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id, slug, status, board2_revealed_at, starts_at, ends_at, created_at
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


def claim_bounty(team_id, bounty_key, invoked_by_user_id, expected_movement_id,
                 testdb=None):
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
            return {'ok': False, 'reason': 'conflict'}

        locked_movement_id, from_sequence = locked
        if locked_movement_id != expected_movement_id:
            db.rollback()
            return {'ok': False, 'reason': 'conflict'}

        board_number = candyland_board.board_of(from_sequence)
        to_sequence = candyland_bounty.destination(
            bounty_key, from_sequence,
            candyland_board.board_final_tile(from_sequence),
        )
        moved = to_sequence != from_sequence

        movement_id = record_movement(
            team_id, 'adjustment', None, from_sequence, to_sequence,
            None, invoked_by_user_id, f'bounty:{bounty_key}', testdb=db,
        )
        try:
            record_bounty_use(
                team_id, board_number, bounty_key, from_sequence, movement_id,
                testdb=db,
            )
        except pymysql.err.IntegrityError:
            db.rollback()
            return {'ok': False, 'reason': 'already_used'}

        refold_team_state(team_id, testdb=db)
        db.commit()
        return {
            'ok': True,
            'bounty_key': bounty_key,
            'board_number': board_number,
            'from_sequence': from_sequence,
            'to_sequence': to_sequence,
            'moved': moved,
            'movement_id': movement_id,
        }
    except Exception:
        db.rollback()
        raise


def move_team(team_id, to_sequence, invoked_by_user_id, expected_movement_id,
              testdb=None):
    # Mod reposition. One transaction mirroring claim_bounty: SELECT ... FOR
    # UPDATE the team_state row, verify the guard, append an append-only
    # 'adjustment' movement row, refold. No update, no delete. The caller has
    # already checked to_sequence != current_sequence (an equal move is
    # ceremony-only, no row).
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
            return {'ok': False, 'reason': 'conflict'}

        locked_movement_id, from_sequence = locked
        if locked_movement_id != expected_movement_id:
            db.rollback()
            return {'ok': False, 'reason': 'conflict'}

        movement_id = record_movement(
            team_id, 'adjustment', None, from_sequence, to_sequence,
            None, invoked_by_user_id, f'mod move by {invoked_by_user_id}',
            testdb=db,
        )
        refold_team_state(team_id, testdb=db)
        db.commit()
        return {
            'ok': True,
            'from_sequence': from_sequence,
            'to_sequence': to_sequence,
            'movement_id': movement_id,
        }
    except Exception:
        db.rollback()
        raise


# --- Board 2 reveal + transition (/candyland doomsday, Phase C wave 2) ---

def team_has_crossed_to_board2(team_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        select 1
          from movement
         where team_id = %s
           and kind = 'board_transition'
         limit 1
    """
    cursor.execute(query, (team_id,))
    return cursor.fetchone() is not None


def set_board2_revealed(event_id, testdb=None):
    # /candyland doomsday: flip the reveal once. The `board2_revealed_at is null`
    # predicate makes a second call a no-op; rowcount tells the caller whether
    # this call is the one that revealed Board 2.
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        update event
           set board2_revealed_at = now()
         where id = %s
           and board2_revealed_at is null
    """
    cursor.execute(query, (event_id,))
    return cursor.rowcount > 0


def mark_board2_leader(team_id, invoked_by_user_id, expected_movement_id,
                       testdb=None):
    # /candyland doomsday marks the named leader as having crossed to Board 2
    # without moving it: a board_transition row BOARD1_SIZE -> BOARD1_SIZE.
    # refold leaves the team on tile 42; team_has_crossed_to_board2 then reports
    # true, so the leader's next roll takes the full-track path, not the
    # trailing teleport. Written before set_board2_revealed so a racing roll
    # cannot teleport the leader in the gap (see the plan's deviation note).
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
        if (locked_movement_id != expected_movement_id
                or locked_sequence != candyland_board.BOARD1_SIZE):
            db.rollback()
            return None

        if team_has_crossed_to_board2(team_id, testdb=db):
            db.rollback()
            return None

        movement_id = record_movement(
            team_id, 'board_transition', None,
            candyland_board.BOARD1_SIZE, candyland_board.BOARD1_SIZE,
            None, invoked_by_user_id, 'board 2 revealed - leader marker',
            testdb=db,
        )
        refold_team_state(team_id, testdb=db)
        db.commit()
        return movement_id
    except Exception:
        db.rollback()
        raise


def teleport_team_to_board2(team_id, invoked_by_user_id, expected_movement_id,
                            testdb=None):
    # A trailing team's first /candyland roll after the reveal: no dice, straight
    # to the first Board 2 tile. board_transition row from wherever it stood to
    # BOARD1_SIZE + 1. Same lock discipline as advance_team_by_roll.
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

        locked_movement_id, from_sequence = locked
        if locked_movement_id != expected_movement_id:
            db.rollback()
            return None

        movement_id = record_movement(
            team_id, 'board_transition', None, from_sequence,
            candyland_board.BOARD1_SIZE + 1, None, invoked_by_user_id,
            'board 2 transition - trailing teleport', testdb=db,
        )
        refold_team_state(team_id, testdb=db)
        db.commit()
        return movement_id
    except Exception:
        db.rollback()
        raise


def get_pending_modifier(team_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        select bu.bounty_key
          from bounty_use bu
         where bu.team_id = %s
           and bu.bounty_key in ('DISADVANTAGE', 'ADVANTAGE', 'DOUBLE_DOWN')
           and bu.movement_id is not null
           and bu.movement_id > coalesce(
                 (select max(m.id) from movement m
                   where m.team_id = %s and m.kind = 'roll'), 0)
         order by bu.movement_id desc
         limit 1
    """
    cursor.execute(query, (team_id, team_id))
    row = cursor.fetchone()
    return row[0] if row else None


def get_last_bounty_since_roll(team_id, testdb=None):
    # The bounty_key of the team's most recent bounty_use since its last roll,
    # or None if it has rolled since (or never used one). Drives the sequencing
    # gate in the cog: a team may not chain bounties across one tile.
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor()

    query = """
        select bu.bounty_key
          from bounty_use bu
         where bu.team_id = %s
           and bu.movement_id is not null
           and bu.movement_id > coalesce(
                 (select max(m.id) from movement m
                   where m.team_id = %s and m.kind = 'roll'), 0)
         order by bu.movement_id desc
         limit 1
    """
    cursor.execute(query, (team_id, team_id))
    row = cursor.fetchone()
    return row[0] if row else None


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


def get_all_tile_threads(event_id, testdb=None):
    db = testdb if testdb else connection.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select tt.id, tt.team_id, tt.tile_sequence, tt.thread_id, tt.state
          from tile_thread tt
          join team t
            on t.id = tt.team_id
         where t.event_id = %s
         order by tt.id
    """
    cursor.execute(query, (event_id,))
    return cursor.fetchall()


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


def move_open_thread_to_tile(team_id, tile_sequence, new_thread_id, testdb=None):
    # Make tile_sequence the team's single open tile thread, pointed at
    # new_thread_id, as one transaction. Used by the bounty claims that replace
    # the tile task (Retreat/Advance move to a new tile; Swap/Double Down stay
    # on the current one). A fresh Discord thread is always created, so if a row
    # already exists for (team_id, tile_sequence) it is repointed at the new
    # thread and reopened rather than inserted (the unique key forbids a second
    # row). Any other open row for the team is closed first, so the one open
    # thread per team invariant never briefly breaks.
    db = testdb if testdb else connection.create_connection()
    db.begin()
    try:
        cursor = db.cursor()
        cursor.execute(
            """
            update tile_thread
               set state = 'closed', closed_at = now()
             where team_id = %s and state = 'open'
            """,
            (team_id,),
        )
        cursor.execute(
            "select id from tile_thread where team_id = %s and tile_sequence = %s",
            (team_id, tile_sequence),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                """
                update tile_thread
                   set thread_id = %s, state = 'open', closed_at = null
                 where id = %s
                """,
                (new_thread_id, row[0]),
            )
        else:
            cursor.execute(
                """
                insert into tile_thread (team_id, tile_sequence, thread_id)
                values (%s, %s, %s)
                """,
                (team_id, tile_sequence, new_thread_id),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise


def clear_event_teams(event_id, testdb=None):
    # Test-only reset: drop every team for the event (FKs cascade to movement,
    # tile_thread, team_state, bounty_use) and send the event back to 'setup'.
    # Keeps the event row. Never call this on a real event.
    db = testdb if testdb else connection.create_connection()
    db.begin()
    try:
        cursor = db.cursor()
        cursor.execute("delete from team where event_id = %s", (event_id,))
        cursor.execute("update event set status = 'setup' where id = %s", (event_id,))
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
