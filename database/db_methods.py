import pymysql

def register_user(db, author):
    cursor = db.cursor()
    display_name = author.nick if author.nick else author.global_name

    query = """
        insert ignore into Discord.user (user_id, username)
        values (%s, %s)
    """
    values = (
        author.id,
        author.name,
    )
    cursor.execute(query, values)

    query = """
        insert ignore into Discord.user_alias (user_id, alias)
        values (%s, %s)
    """
    values = (
        author.id,
        display_name,
    )
    cursor.execute(query, values)

