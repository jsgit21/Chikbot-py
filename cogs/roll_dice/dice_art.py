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


def render_inline_lines(total):
    """render() with each row wrapped in its own inline-code span.

    A ``` block stretches to the full Discord message width; per-line inline code
    keeps each row only as wide as its text. Rows are padded to a common width so
    the pills line up. Discord trims one leading/trailing space inside inline
    code, so pad with an extra space on each side to protect the alignment.
    """
    art = [line.rstrip() for line in render(total).split('\n')]
    width = max(len(line) for line in art)
    return '\n'.join(f'` {line.ljust(width)} `' for line in art)
