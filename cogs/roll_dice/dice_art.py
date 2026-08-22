_DIE_ART_LINES = [
    '       .-------. ',
    '      /       /|   ',
    '     /_______/o|  ',
    '     | o     | | ',
    '     |   o   |o/ ',
    '     |     o |/  ',
    "     '-------' ",
]
_RESULT_ROW = 1
_RESULT_WIDTH = 7


def render(total):
    lines = list(_DIE_ART_LINES)
    face = str(total).center(_RESULT_WIDTH)
    lines[_RESULT_ROW] = f'      /{face}/|   '
    return '\n'.join(lines)
