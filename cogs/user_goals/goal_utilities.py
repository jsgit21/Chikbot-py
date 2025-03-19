from datetime import date

def format_goals(goals, verbose=False, sub_indent=True):

    goal_list = []
    for goal in goals:
        goal_row = f'**{goal["rnk"]}**: {goal["goal"]}'

        if goal['completed']:
            goal_row = f'~~{goal_row}~~'

        bullet_row = (f'{goal_row}')
        if goal['sub_goal']:
            # Add spacing
            bullet_row = f'\t\t{bullet_row}'

        goal_list.append(bullet_row)

        if verbose:
            created_date = f'__Created__: {goal["insert_date"]}'
            completed_date = f'__Completed__: {goal["completed_date"]}'

            if goal['completed']:
                goal_dates = ' '.join([created_date, completed_date])
            else:
                goal_dates = created_date

            if goal['sub_goal'] and sub_indent:
                # Ridiculous way I need to add empty space for discord
                goal_dates = f'-#  ** ** ** ** ** ** ** ** ** ** {goal_dates}'
            else:
                goal_dates = f'-# {goal_dates}'

            goal_list.append(goal_dates)

    return '\n'.join(goal_list)


def days_since_date(previous_date):

    today = date.today()
    return (today - previous_date).days


def format_detailed_goal(goal):

    string_list = []
    formatted_goal = format_goals([goal], verbose=True, sub_indent=False)
    formatted_goal = formatted_goal.replace('~~', '')
    string_list.append(formatted_goal)

    create_days = days_since_date(goal['insert_date'])
    string_list.append(f'-# Days since creation: **{create_days}**')

    if goal['completed_date']:
        complete_days = days_since_date(goal['completed_date'])
        string_list.append(f'-# Days since completion: **{complete_days}**')
        string_list.append(f'-# Days to complete: **{create_days-complete_days}**')

    return '\n'.join(string_list)


