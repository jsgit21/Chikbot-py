import pymysql
import database.db_methods as database

def add_goal(user_id, goal, parent_goal_number, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    parent_id = None
    if parent_goal_number:
        parent_row = get_goals(user_id, goal_number=parent_goal_number, type='incomplete')

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

def get_goals(user_id, goal_number=None, type=None, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    if type not in [None, 'complete', 'incomplete']:
        raise Exception(f'Incorrect type: {type}')

    goals_view = 'ordered_goals'
    if type is not None:
        goals_view = f'ordered_{type}_goals'


    query = """
        select id,
               rnk,
               goal,
               sub_goal,
               completed,
               cast(insert_date as date) as insert_date,
               cast(completed_date as date) as completed_date
          from {view}
         where user_id = %s
    """.format(view=goals_view)
    if goal_number:
        query += f'and rnk = %s'
        cursor.execute(query, (user_id, goal_number))
        return cursor.fetchone()

    cursor.execute(query, (user_id))
    return cursor.fetchall()

def complete_goal(user_id, goal_number, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    # Get the goal info before deleting
    row = get_goals(user_id, goal_number, type='incomplete')

    query = """
        update user_goal u
          join ordered_incomplete_goals o
            on u.id = o.id
           set u.completed = True,
               u.completed_date = now()
         where u.user_id = %s
           and o.rnk = %s
    """
    values = (
        user_id,
        goal_number,
    )
    cursor.execute(query, values)

    return row

def delete_goal(user_id, goal_number, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    row = get_goals(user_id, goal_number=goal_number, type='incomplete')
    if row is None:
        return

    query = """
        delete u
          from user_goal u
          join ordered_incomplete_goals o
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

def edit_goal(user_id, goal_number, goal, testdb=None):
    db = testdb if testdb else database.create_connection()
    cursor = db.cursor()

    row = get_goals(user_id, goal_number=goal_number, type='incomplete')
    if row is None:
        return

    query = """
        update user_goal u
          join ordered_incomplete_goals o
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

