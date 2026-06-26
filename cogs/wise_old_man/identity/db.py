import pymysql

import database.db_methods as database


def _normalize_rsn(rsn):
    # wom_group stores display names lowercased, and OSRS dedupes hyphens vs spaces.
    return rsn.replace('-', ' ').lower()


def link_rsn(rsn, user_id, testdb=None):
    """Link an RSN (must already exist in wom_group) to a Discord user.

    Keyed by the stable wom_user_id, so the link survives later renames. Returns
    the matched wom_group row, or None if the RSN is not in the group. The caller
    is responsible for ensuring the user row exists (register_user).
    """
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute(
        'select wom_user_id, rsn from wom_group where rsn = %s',
        (_normalize_rsn(rsn),)
    )
    member = cursor.fetchone()
    if member is None:
        return None

    query = """
        insert into wom_link (wom_user_id, user_id)
             values (%s, %s)
        on duplicate key update user_id = values(user_id)
    """
    cursor.execute(query, (member['wom_user_id'], user_id))
    return member


def unlink_rsn(rsn, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    query = """
        delete wl
          from wom_link wl
          join wom_group wg
            on wl.wom_user_id = wg.wom_user_id
         where wg.rsn = %s
    """
    cursor.execute(query, (_normalize_rsn(rsn),))
    return cursor.rowcount


def set_preferred_alias(user_id, alias, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    cursor.execute('update user set preferred_alias = %s where user_id = %s', (alias, user_id))
    return cursor.rowcount


def get_unlinked_members(testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select wg.wom_user_id, wg.rsn, wg.`rank`
          from wom_group wg
          left join wom_link wl
            on wg.wom_user_id = wl.wom_user_id
         where wl.wom_user_id is null
         order by wg.rsn
    """
    cursor.execute(query)
    return cursor.fetchall()


def whois_rsn(rsn, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select wg.wom_user_id, wg.rsn, wl.user_id, u.username, u.preferred_alias
          from wom_group wg
          join wom_link wl
            on wg.wom_user_id = wl.wom_user_id
          join user u
            on wl.user_id = u.user_id
         where wg.rsn = %s
    """
    cursor.execute(query, (_normalize_rsn(rsn),))
    return cursor.fetchone()


def whois_user(user_id, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select wg.wom_user_id, wg.rsn, u.preferred_alias
          from wom_link wl
          join wom_group wg
            on wl.wom_user_id = wg.wom_user_id
          join user u
            on wl.user_id = u.user_id
         where wl.user_id = %s
         order by wg.rsn
    """
    cursor.execute(query, (user_id,))
    return cursor.fetchall()


def discord_user_for_rsn(rsn, testdb=None):
    """Return (user_id, preferred_alias) for a linked RSN, or None.

    Resolves the name through wom_group, so it follows renames automatically.
    """
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select u.user_id, u.preferred_alias
          from wom_group wg
          join wom_link wl
            on wg.wom_user_id = wl.wom_user_id
          join user u
            on wl.user_id = u.user_id
         where wg.rsn = %s
    """
    cursor.execute(query, (_normalize_rsn(rsn),))
    return cursor.fetchone()


def discord_user_for_wom_id(wom_user_id, testdb=None):
    """Return (user_id, preferred_alias) for a linked WOM player id, or None.

    The rename-proof lookup: competition winners are resolved by their stable
    WOM player id (participations[].player.id), never by display name.
    """
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select u.user_id, u.preferred_alias
          from wom_link wl
          join user u
            on wl.user_id = u.user_id
         where wl.wom_user_id = %s
    """
    cursor.execute(query, (wom_user_id,))
    return cursor.fetchone()
