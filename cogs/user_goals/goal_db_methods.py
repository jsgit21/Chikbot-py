import pymysql

def add_goal(db, user_id, goal, parent_goal_number):
    cursor = db.cursor()

    parent_id = None
    if parent_goal_number:
        parent_row = get_goals(db, user_id, parent_goal_number)

        if parent_row is None:
            return
        parent_id = parent_row['id']

    query = """
        insert into user_goal (user_id, goal, parent_id)
        values(%s, %s, %s)
    """
    values = (
        user_id,
        goal,
        parent_id,
    )
    cursor.execute(query, values)
    return cursor.lastrowid


def get_goals(db, user_id, goal_number=None):
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        select id,
               rnk,
               goal,
               sub_goal,
               completed,
               cast(insert_date as date) as insert_date,
               cast(completed_date as date) as completed_date
          from ordered_goals
         where user_id = %s
    """
    if goal_number:
        query += f'and rnk = %s'
        cursor.execute(query, (user_id, goal_number))
        return cursor.fetchone()

    cursor.execute(query, (user_id))
    return cursor.fetchall()

def complete_goal(db, user_id, goal_number):
    cursor = db.cursor()

    # Flip the completed value, so this function can be used to add or
    # remove completion

    query = """
        update user_goal u
          join ordered_goals o
            on u.id = o.id
           set u.completed = not u.completed,
               u.completed_date = now()
         where u.user_id = %s
           and o.rnk = %s
    """
    values = (
        user_id,
        goal_number,
    )
    cursor.execute(query, values)

    row = get_goals(db, user_id, goal_number)
    return row

def delete_goal(db, user_id, goal_number):
    cursor = db.cursor()

    row = get_goals(db, user_id, goal_number)
    if row is None:
        return

    query = """
        delete u
          from user_goal u
          join ordered_goals o
            on u.id = o.id
         where u.user_id = %s
           and o.rnk = %s
    """
    values = (
        user_id,
        goal_number,
    )
    cursor.execute(query, values)

    return row

def edit_goal(db, user_id, goal_number, goal):
    cursor = db.cursor()

    row = get_goals(db, user_id, goal_number)
    if row is None:
        return

    query = """
        update user_goal u
          join ordered_goals o
            on u.id = o.id
           set u.goal = %s
         where u.user_id = %s
           and o.rnk = %s
    """
    values = (
        goal,
        user_id,
        goal_number,
    )
    cursor.execute(query, values)

    return row

