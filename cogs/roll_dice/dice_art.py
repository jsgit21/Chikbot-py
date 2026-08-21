import random

_DIE_ART_LINES = [
    '   ______',
    '  /     /|',
    ' /_____/ |',
    ' |     | |',
    ' |     | /',
    ' |_____|/',
]
_RESULT_ROW = 3


def roll(sides):
    return random.randint(1, sides)


def render(sides, result):
    lines = list(_DIE_ART_LINES)
    lines[_RESULT_ROW] = f'{lines[_RESULT_ROW]}     Result: {result}'
    return '\n'.join(lines)
