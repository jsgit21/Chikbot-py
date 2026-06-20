
def format_wom_whitelist_changes(changes):
    final_output = ['> Changes to the WOM Whitelist']

    inserts_msg = '__Inserts__:\n'
    for insert in changes['inserts']:
        new_name = insert['new_name']
        inserts_msg += f'`{new_name}`\n'

    if len(changes['inserts']) > 0:
        final_output.append(inserts_msg)

    updates_msg = '__Updates__:\n'
    for update in changes['updates']:
        old_name = update['old_name']
        new_name = update['new_name']
        updates_msg += f'`{old_name:<12}` -> `{new_name:<12}`\n'

    if len(changes['updates']) > 0:
        final_output.append(updates_msg)

    deletes_msg = '__Deletes__:\n'
    for delete in changes['deletes']:
        old_name = delete['old_name']
        deletes_msg += f'`{old_name}`\n'

    if len(changes['deletes']) > 0:
        final_output.append(deletes_msg)

    final_output.append('-# The WOM Whitelist controls Dink access')
    return '\n'.join(final_output)

