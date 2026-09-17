# One continuous track: Board 1 is tiles 1..BOARD1_SIZE. The roll guard clamps
# here until /candyland doomsday (Phase C) opens the tiles past it.
BOARD1_SIZE = 60


def total_tiles(database):
    """The last tile of the whole track: the highest tile_sequence among
    Major tasks. Phase F: replaces the BOARD1_SIZE + BOARD2_SIZE constant now
    that Majors live in candyland.task."""
    return database.get_max_major_tile_sequence()


def board_of(sequence):
    """Which board a tile sequence is on: 1 for Board 1, 2 for Board 2."""
    return 1 if sequence <= BOARD1_SIZE else 2


def minor_count_for_tile(tile_sequence):
    """How many Minors a tile carries: 2 past the doomsday tile (Board 2),
    1 otherwise. By tile_sequence alone, independent of whether /candyland
    doomsday has actually fired yet."""
    return 2 if tile_sequence > BOARD1_SIZE else 1


def board_final_tile(sequence, total):
    """The last tile of whichever board `sequence` is on."""
    return BOARD1_SIZE if board_of(sequence) == 1 else total


def is_board_final_tile(sequence, total):
    return sequence == BOARD1_SIZE or sequence == total


def is_board_first_tile(sequence):
    return sequence == 1 or sequence == BOARD1_SIZE + 1


def is_board_edge_tile(sequence, total):
    """The first or last tile of either board. No bounty may be taken here."""
    return is_board_first_tile(sequence) or is_board_final_tile(sequence, total)
