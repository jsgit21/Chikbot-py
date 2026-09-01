# The board size is a constant until Phase F, which replaces it with:
#   select max(tile_sequence) from tile
# One continuous track: Board 1 is tiles 1..BOARD1_SIZE. The roll guard clamps
# here until /candyland doomsday (Phase C) opens the tiles past it.
BOARD1_SIZE = 42
BOARD2_SIZE = 23  # TODO: confirm Board 2 tile count against casual-gmers content
TOTAL_TILES = BOARD1_SIZE + BOARD2_SIZE


def board_of(sequence):
    """Which board a tile sequence is on: 1 for Board 1, 2 for Board 2."""
    return 1 if sequence <= BOARD1_SIZE else 2


def board_final_tile(sequence):
    """The last tile of whichever board `sequence` is on."""
    return BOARD1_SIZE if board_of(sequence) == 1 else TOTAL_TILES


def is_board_final_tile(sequence):
    return sequence == BOARD1_SIZE or sequence == TOTAL_TILES


def is_board_first_tile(sequence):
    return sequence == 1 or sequence == BOARD1_SIZE + 1


def is_board_edge_tile(sequence):
    """The first or last tile of either board. No bounty may be taken here."""
    return is_board_first_tile(sequence) or is_board_final_tile(sequence)
