# The board size is a constant until Phase F, which replaces it with:
#   select max(tile_sequence) from tile
# One continuous track: Board 1 is tiles 1..BOARD1_SIZE. The roll guard clamps
# here until /candyland doomsday (Phase C) opens the tiles past it.
BOARD1_SIZE = 42
