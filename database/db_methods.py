import pymysql

def create_connection(database='Discord', cursor=pymysql.cursors.Cursor):
    connection = pymysql.connect(
        database=database,
        read_default_file='~/.my.cnf',
        autocommit=True,
        cursorclass=cursor
    )
    return connection

def register_user(author, testdb=None):
    db = testdb if testdb else create_connection()
    cursor = db.cursor()
    display_name = author.nick if author.nick else author.global_name

    query = """
        insert ignore into user (user_id, username)
        values (%s, %s)
    """
    values = (
        author.id,
        author.name,
    )
    cursor.execute(query, values)

    query = """
        insert ignore into user_alias (user_id, alias)
        values (%s, %s)
    """
    values = (
        author.id,
        display_name,
    )
    cursor.execute(query, values)

# Update local wom group and return changes
def update_local_wom_group(group):
    db = create_connection(cursor=pymysql.cursors.DictCursor)
    cursor = db.cursor()

    changes = {
        'total_changes': 0,
        'updates': None,
        'inserts': None,
        'deletes': None,
    }

    query = """
        create temporary table wom_group_tmp like wom_group;
    """
    cursor.execute(query)

    query = """
        insert into wom_group_tmp (wom_user_id, rsn, `rank`)
            values (%s, %s, %s)
    """
    cursor.executemany(query, group)

    # Get updates
    query = """
        select w.wom_user_id, w.rsn as old_name, t.rsn as new_name
          from wom_group w
          join wom_group_tmp t
            on w.wom_user_id = t.wom_user_id
         where w.rsn <> t.rsn
    """
    cursor.execute(query)
    changes['updates'] = cursor.fetchall()
    changes['total_changes'] += cursor.rowcount

    # Process updates
    for update in changes['updates']:
        query = """
            update wom_group
               set rsn = %s
             where wom_user_id = %s
               and rsn = %s
        """
        values = (update['new_name'], update['wom_user_id'], update['old_name'])
        cursor.execute(query, values)

    # Get inserts
    query = """
        select t.wom_user_id, t.rsn as new_name, t.rank
          from wom_group_tmp t
         where not exists (
            select 1
              from wom_group w
             where t.wom_user_id = w.wom_user_id
         )
    """
    cursor.execute(query)
    changes['inserts'] = cursor.fetchall()
    changes['total_changes'] += cursor.rowcount

    # Process inserts
    for insert in changes['inserts']:
        query = """
            insert into wom_group (wom_user_id, rsn, `rank`)
            values (%s, %s, %s)
        """
        values = (insert['wom_user_id'], insert['new_name'], insert['rank'])
        cursor.execute(query, values)

    # Get deletes
    query = """
        select w.wom_user_id, w.rsn as old_name
          from wom_group w
         where not exists (
            select 1
              from wom_group_tmp t
             where w.wom_user_id = t.wom_user_id
         )
    """
    cursor.execute(query)
    changes['deletes'] = cursor.fetchall()
    changes['total_changes'] += cursor.rowcount

    # Process deletes
    for delete in changes['deletes']:
        query = """
            delete from wom_group
             where wom_user_id = %s
        """
        values = (delete['wom_user_id'])
        cursor.execute(query, values)

    return changes


def check_local_wom(rsn):
    db = create_connection()
    cursor = db.cursor()

    query = """
        select *
          from wom_group where rsn = %s
    """
    active_member = cursor.execute(query, rsn)
    return active_member

def register_latest_dink_transaction(channel, message_id):
    db = create_connection()
    cursor = db.cursor()

    query = """
        update latest_dink_transactions
           set message_id = %s
         where channel_name = %s
    """
    cursor.execute(query, (message_id, channel))
    return

def get_latest_dink_transaction(channel):
    db = create_connection()
    cursor = db.cursor()

    query = """
        select message_id
          from latest_dink_transactions
         where channel_name = %s
    """
    cursor.execute(query, channel)
    message_id = cursor.fetchone()[0]
    return message_id

