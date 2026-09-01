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


_FRAME_MARGIN = 5


def render(total):
    lines = list(_DIE_ART_LINES)
    face = str(total).center(_RESULT_WIDTH)
    lines[_RESULT_ROW] = f'      /{face}/|   '
    return '\n'.join(lines)


def render_framed(total):
    """render() inside a full rectangular border, alignment preserved.

    Discord always stretches a ``` block to the message width; the border makes
    that width read as a deliberate panel instead of art stranded in whitespace.
    The cube's leading spaces carry the isometric alignment, so pad, don't strip.
    """
    art = [line.rstrip() for line in render(total).split('\n')]
    inner = max(len(line) for line in art) + 2 * _FRAME_MARGIN
    pad = ' ' * _FRAME_MARGIN
    border = '+' + '-' * inner + '+'
    body = ['|' + (pad + line).ljust(inner) + '|' for line in art]
    return '\n'.join([border, *body, border])
