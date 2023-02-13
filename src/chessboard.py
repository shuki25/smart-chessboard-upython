"""
Chessboard class:

A class that handles the decoding hall sensors input and translate into a chessboard
and its pieces. It does not handle the chess logic, only the board representation
using bitboards. However, it does track which pieces in each position on the board
using a list of 64 squares. The list is indexed by the square number, and the value
is the piece type. The piece type is a string, and can be one of the following:

    "P" - white pawn
    "p" - black pawn
    "N" - white knight
    "n" - black knight
    "B" - white bishop
    "b" - black bishop
    "R" - white rook
    "r" - black rook
    "Q" - white queen
    "q" - black queen
    "K" - white king
    "k" - black king
    " " - empty square

The class also has a method to print the board to the console, and a method to
convert the board to a FEN string and back. The FEN string is a standard way to
represent a chessboard, and is used by chess engines and chess databases.

The bitboards are represented as 64-bit integers, and are used to track the
positions of the pieces. The bitboards use setwise operations to test the
board squares to indicate if the square is occupied by a piece.

"""
import machine
import uasyncio
from io_expander import IOExpander

RANK = ["1", "2", "3", "4", "5", "6", "7", "8"]
FILE = ["a", "b", "c", "d", "e", "f", "g", "h"]
PRINT_RANK = ["8", "7", "6", "5", "4", "3", "2", "1"]
FEN_STARTING_POSITION = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

IO_EXPANDER_0_ADDRESS = 0x20
IO_EXPANDER_1_ADDRESS = 0x21
IO_EXPANDER_2_ADDRESS = 0x22
IO_EXPANDER_3_ADDRESS = 0x23

IO_EXPANDER_TILE = [
    0x01,
    0x02,
    0x04,
    0x08,
    0x10,
    0x20,
    0x40,
    0x80,
    0x1000,
    0x2000,
    0x4000,
    0x8000,
    0x0100,
    0x0200,
    0x0400,
    0x0800,
]

IO_EXPANDER_LIST = [IO_EXPANDER_0_ADDRESS, IO_EXPANDER_1_ADDRESS, IO_EXPANDER_2_ADDRESS, IO_EXPANDER_3_ADDRESS]
IO_EXPANDER_MASK = [0xFFFF, 0xFFFF0000, 0xFFFF00000000, 0xFFFF000000000000]
IO_EXPANDER_SHIFT = [0, 16, 32, 48]

INVERSE_MASK = 0xFFFFFFFFFFFFFFFF
STARTING_POSITION = 0xFFFF00000000FFFF
CASTLING_WHITE_KING = 0x0000000000000060
CASTLING_WHITE_QUEEN = 0x000000000000000C
CASTLING_BLACK_KING = 0x6000000000000000
CASTLING_BLACK_QUEEN = 0x0C00000000000000


class Chessboard:
    io_expander = []
    board = list(" " * 64)
    bitboard = list(" " * 64)
    board_coords = {}
    board_coords_reverse = {}
    board_status = 0xFFFF00000000FFFF
    rgb_leds: machine.Pin

    def __init__(self, i2c: machine.I2C, address_list: list, rgb_leds: machine.Pin):
        """
        Initialize the chessboard

        :param i2c: I2C bus
        :param address_list: List of IO expander addresses
        :param rgb_leds: WS2813C RGB LED pin

        :return: Class instance
        """
        self.board_status = 0xFFFF00000000FFFF
        if isinstance(i2c, machine.I2C):
            self.i2c = i2c
        elif i2c is None:
            raise Exception("i2c parameter is required")
        else:
            raise Exception("i2c is not an I2C object")
        if isinstance(address_list, list):
            self.address_list = address_list
        elif address_list is None:
            raise Exception("address_list parameter is required")
        else:
            raise Exception("address_list is not a list")
        if isinstance(rgb_leds, machine.Pin):
            self.rgb_leds = rgb_leds
        elif rgb_leds is None:
            raise Exception("rgb_leds parameter is required")
        else:
            raise Exception("rgb_leds is not a Pin object")

        # Initialize IO expanders with polarity inversion on all pins
        for i, address in enumerate(self.address_list):
            self.io_expander.append(IOExpander(self.i2c, address))
            self.io_expander[i].polarity_inversion_port_0(0xFF)
            self.io_expander[i].polarity_inversion_port_1(0xFF)

        self.generate_board_coords()
        self.parse_fen(FEN_STARTING_POSITION)

    def parse_fen(self, fen: str):
        """
        Parse a FEN string and set the piece positions on the board. Ignores the turn to move,
        castling availability, en passant square, halfmove clock, and fullmove number.

        :param fen: FEN string

        :return: None
        """
        fen = fen.split(" ")
        board = fen[0]
        board = board.split("/")
        self.board = list(" " * 64)
        i = 8
        for rank in board:
            j = 0
            for char in rank:
                if char.isdigit():
                    j += int(char)
                else:
                    board_index = (i - 1) * 8 + j
                    self.board[board_index] = char
                    j += 1
            i -= 1

    def reset_board(self):
        """
        Reset the board to the starting position

        :return: None
        """
        self.parse_fen(FEN_STARTING_POSITION)

    def generate_board_coords(self):
        """
        Generate a dictionary of board coordinates and bit positions for each IO expander

        :return: None
        """
        i = 0
        j = 0
        for rank in RANK:
            for file in FILE:
                self.board_coords[file + rank] = (j, IO_EXPANDER_TILE[i])
                reverse_index = IO_EXPANDER_TILE[i] << IO_EXPANDER_SHIFT[j]
                self.board_coords_reverse[reverse_index] = file + rank
                i += 1
                if i >= 16:
                    i = 0
                    j += 1

    def read_board(self):
        """
        Read the board state from the IO expanders

        :return: None
        """
        self.board_status = 0
        for i, gpio in enumerate(self.io_expander):
            data = gpio.read_input_port()
            # print("IO Expander %d: %x" % (i, data))
            shift_data = data << IO_EXPANDER_SHIFT[i]
            self.board_status |= shift_data
        for square in self.board_coords.keys():
            data = (self.board_status & IO_EXPANDER_MASK[self.board_coords[square][0]]) >> IO_EXPANDER_SHIFT[
                self.board_coords[square][0]
            ]
            board_idx = self.algebraic_to_board_index(square)
            if data & self.board_coords[square][1]:
                self.bitboard[board_idx] = 1
            else:
                self.bitboard[board_idx] = 0

    def print_board(self):
        """
        Print the board state to the console

        :return: None
        """
        i = 8
        for rank in PRINT_RANK:
            print("  ---------------------------------")
            print(rank, end=" |")
            for j, file in enumerate(FILE):
                square = (i - 1) * 8 + j
                print(" %s |" % self.board[square], end="")
            print()
            i -= 1
        print("  ---------------------------------")
        print("  |", end="")
        for file in FILE:
            print("", file.upper(), end=" |")
        print()
        print("  ---------------------------------")

    def print_bitboard(self):
        """
        Print the board state to the console in bitboard format

        :return: None
        """
        i = 8
        for rank in PRINT_RANK:
            print("  ---------------------------------")
            print(rank, end=" |")
            for j, file in enumerate(FILE):
                square = (i - 1) * 8 + j

                print(" %s |" % self.bitboard[square], end="")
            print()
            i -= 1
        print("  ---------------------------------")
        print("  |", end="")
        for file in FILE:
            print("", file.upper(), end=" |")
        print()
        print("  ---------------------------------")

    def convert_bitboard_to_int(self, bitboard: list = None) -> int:
        """
        Convert a bitboard to an integer

        :param bitboard: Bitboard

        :return: Integer
        """
        bitboard_int = 0

        if bitboard is None:
            bitboard = self.bitboard

        for i in range(63, -1, -1):
            bitboard_int <<= 1
            if bitboard[i]:
                bitboard_int |= 1

        return bitboard_int

    def get_board(self):
        """
        Return the board state and piece positions

        :return: Tuple of board_status and piece positions
        """
        return self.board_status, self.board

    def count_pieces(self, current_board=None):
        """
        Count the number of pieces on the board
        """
        if current_board is None:
            current_board = self.board_status
        return str(bin(current_board)).count("1")

    def update_board_move(self, move: tuple):
        """
        Update the board state with a move

        :param move: Move in long algebraic notation

        :return: None
        """
        if not isinstance(move, tuple):
            raise Exception("move is not a tuple")
        start = self.algebraic_to_board_index(move[0])
        end = self.algebraic_to_board_index(move[1])
        piece = self.board[start]
        self.board[start] = " "
        self.board[end] = piece

    def update_castling_move(self, color: str, side: str):
        """
        Update the board state with a castling move

        :param color: Color of the player
        :param side: Side of the board

        :return: None
        """
        if color == "w":
            if side == "K":
                self.board[4] = " "
                self.board[5] = "R"
                self.board[6] = "K"
                self.board[7] = " "
            else:
                self.board[0] = " "
                self.board[1] = " "
                self.board[2] = "K"
                self.board[3] = "R"
                self.board[4] = " "
        else:
            if side == "K":
                self.board[60] = " "
                self.board[61] = "r"
                self.board[62] = "k"
                self.board[63] = " "
            else:
                self.board[56] = " "
                self.board[57] = " "
                self.board[58] = "k"
                self.board[59] = "r"
                self.board[60] = " "

    def check_castling_positions(self, color: str, side: str, current_board=None):
        """
        Check if the king and rook are in the correct positions for castling

        :param color: Color of the king
        :param side: Side of the king
        :param current_board: Current board state

        :return: True if castling position is correct, False otherwise
        """
        if current_board is None:
            current_board = self.board_status

        if color == "w":
            if side == "K" and current_board & CASTLING_WHITE_KING:
                return True
            elif side == "Q" and current_board & CASTLING_WHITE_QUEEN:
                return True
        elif color == "b":
            if side == "K" and current_board & CASTLING_BLACK_KING:
                return True
            elif side == "Q" and current_board & CASTLING_BLACK_QUEEN:
                return True
        return False

    def detect_move_positions(self, prev_state, new_state):
        """
        Deduce the positions of a piece moved from old position to new position
        based on previous and new board states

        :param prev_state: Previous board state
        :param new_state: New board state

        :return: Tuple of old and new positions
        """
        new_pos_coord = new_state & (prev_state ^ INVERSE_MASK)
        old_pos_coord = prev_state & (new_state ^ INVERSE_MASK)

        new_pos = self.coord_to_algebraic(new_pos_coord)
        old_pos = self.coord_to_algebraic(old_pos_coord)

        return old_pos, new_pos

    def detect_capture_move_positions(self, prev_state, capturing_state, captured_state):
        """
        Detect the positions of a piece captured from old position to new position

        :param prev_state: Previous board state
        :param capturing_state: Board state after the capturing piece is lifted off the board
        :param captured_state: Board state after piece is captured

        :return: Tuple of old position and captured position (algebraic notation)
        """
        capturing_piece = prev_state & (capturing_state ^ INVERSE_MASK)
        captured_piece = capturing_state & (captured_state ^ INVERSE_MASK)

        capturing = self.coord_to_algebraic(capturing_piece)
        captured = self.coord_to_algebraic(captured_piece)

        return capturing, captured

    def coord_to_algebraic(self, coord):
        """
        Translate a coordinate to algebraic notation

        :param coord: Coordinate to translate
        :return: Algebraic notation
        """
        if coord in self.board_coords_reverse.keys():
            return self.board_coords_reverse[coord]
        else:
            print("Invalid coordinate: %x" % coord)

    def algebraic_to_board_index(self, algebraic):
        """
        Translate algebraic notation to a board index

        :param algebraic: board index
        :return: board index
        """
        try:
            if algebraic.lower() in self.board_coords.keys():
                return RANK.index(algebraic[1]) * 8 + FILE.index(algebraic[0].lower())
            else:
                print("Invalid algebraic notation: %s" % algebraic)
        except Exception as e:
            print("Exception: %s" % e)

    async def reset_board_to_starting_position(self):
        """
        Reset the board to the starting position

        :return: None
        """
        self.read_board()
        if self.board_status == STARTING_POSITION:
            print("Board is already in starting position")
            self.parse_fen(FEN_STARTING_POSITION)
            return True
        else:
            print("Please reset the board to the starting position")
            while True:
                self.read_board()
                if self.board_status == STARTING_POSITION:
                    print("Board is in starting position")
                    self.parse_fen(FEN_STARTING_POSITION)
                    return True
                else:
                    await uasyncio.sleep_ms(300)
