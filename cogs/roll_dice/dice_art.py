_DIE_ART_LINES = [
    '      .-------.   ',
    '     /       /|   ',
    '    /_______/o|   ',
    '    | o     | |   ',
    '    |   o   |o/   ',
    '    |     o |/    ',
    "    '-------'     ",
]
_RESULT_ROW = 1
_RESULT_WIDTH = 7


def render(total):
    art = list(_DIE_ART_LINES)
    face = str(total).center(_RESULT_WIDTH)
    art[_RESULT_ROW] = f'     /{face}/|   '
    width = max(len(line) for line in art)

    formatted_lines = [f'`{line.ljust(width)} `' for line in art]
    return '\n'.join(formatted_lines)

