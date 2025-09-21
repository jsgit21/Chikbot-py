import pymysql

def create_connection(database='Discord'):
    connection = pymysql.connect(
        database=database,
        read_default_file='~/.my.cnf',
        autocommit=True,
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

# Save the list of wom group to database for reference
def update_local_wom_group(group):
    db = create_connection()
    cursor = db.cursor()

    query = """
        create temporary table wom_group_tmp like wom_group;
    """
    cursor.execute(query)

    query = """
        insert into wom_group_tmp (wom_user_id, rsn, `rank`)
        values (%s, %s, %s)
    """
    cursor.executemany(query, group)

    # Insert and update new members locally
    # A duplicate key would occure if a player changes their name
    query = """
        insert into wom_group
        select * from wom_group_tmp tmp
        on duplicate key update rsn = tmp.rsn
    """
    cursor.execute(query)

    # Delete members locally not in group
    query = """
        delete from wom_group w
         where not exists (
            select 1
              from wom_group_tmp t
             where w.rsn = t.rsn
         )
    """
    cursor.execute(query)

def check_local_wom(rsn):
    db = create_connection()
    cursor = db.cursor()

    query = """
        select *
          from wom_group where rsn = %s
    """
    active_member = cursor.execute(query, rsn)
    return active_member

