# Board sizes are a constant until Phase F. Phase F replaces this with:
#   select max(tile_sequence) from tile where board_slug = %s
BOARD_SIZES = {
    'standard': 42,
    'hard': 23,
}
