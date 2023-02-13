"""
Chess Class:

This class is used to represent a chess game. It is used to store the
current state of the game, and to provide methods for making moves and
checking the validity of moves.

The board is represented as a list of 64 characters. The characters
are as follows:

    ' ' - empty square
    'P' - white pawn
    'N' - white knight
    'B' - white bishop
    'R' - white rook
    'Q' - white queen
    'K' - white king
    'p' - black pawn
    'n' - black knight
    'b' - black bishop
    'r' - black rook
    'q' - black queen
    'k' - black king

The board is indexed from 0 to 63, with 0 being the a1 square, and 63
being the h8 square. Other game state is stored as follows:

    self.turn - the side to move, either 'w' or 'b'
    self.castling - a list of castling rights, either 'K', 'Q', 'k', or 'q'
    self.enpassant - the en passant square, or '-' if there is no en passant
    self.halfmove - the number of halfmoves since the last capture or pawn move
    self.fullmove - the number of the full move. It starts at 1, and is
                    incremented after Black's move.

The class provides the following methods:

    __init__(self, fen=None) - initialize the game state. If fen is
        provided, the game state is set according to the FEN string.
        Otherwise, the game state is set to the standard starting position.
    __str__(self) - return a string representation of the board.
    __getitem__(self, index) - return the character at the given board index.
    __setitem__(self, index, value) - set the character at the given board
        index to the given value.
    make_move(self, move) - make the given move if it is valid. The move should
        be in long algebraic notation. If the move is valid, the game state
        is updated and the function returns True. If the move is invalid,
        the game state is not changed and the function returns False.
    is_check(self) - return True if the side to move is in check, and False
        otherwise.
    is_checkmate(self) - return True if the side to move is in checkmate,
        and False otherwise.
    is_stalemate(self) - return True if the side to move is in stalemate,
        and False otherwise.

"""

import sys

if sys.implementation.name == "micropython":
    import ure
else:
    import re as ure

RANK = ["1", "2", "3", "4", "5", "6", "7", "8"]
FILE = ["a", "b", "c", "d", "e", "f", "g", "h"]
PROMOTED_PIECES = ["N", "B", "R", "Q"]
MOVE_NOTATION_REGEX = r"([a-h][1-8])?([-x])?([a-h][1-8])(=?[NBRQnbrq])?(e\.p\.)?"
DEBUG = 0  # 0 = no debug, 1 = debug, 2 = verbose debug

SEGOE_CHESS_FONT_PIECES_LIGHT = {
    "P": 0x70,
    "N": 0x6E,
    "B": 0x62,
    "R": 0x72,
    "Q": 0x71,
    "K": 0x6B,
    "p": 0x6F,
    "n": 0x6D,
    "b": 0x76,
    "r": 0x74,
    "q": 0x77,
    "k": 0x6C,
}
SEGOE_CHESS_FONT_PIECES_DARK_OFFSET = 0x20
SEGOE_CHESS_FONT_RANK = [0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7]
SEGOE_CHESS_FONT_FILE = [0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF]
SEGOE_CHESS_FONT_CORNER = 0x44
SEGOE_CHESS_FONT_EMPTY = [0x20, 0x2B]
SEGOE_CHESS_FONT_DOT = [0x2E, 0x3A]
SEGOE_CHESS_FONT_X = [0x78, 0x58]


def move_notation(
    from_square: int,
    to_square: int,
    capture: bool = False,
    promotion: str = "",
    enpassant: bool = False,
    castle: bool = False,
) -> str:
    """
    Translate board indices to algebraic notation

    :param from_square: board index
    :param to_square: board index
    :param capture: True if captured, False otherwise
    :param promotion: promotion piece, or None if no promotion
    :param enpassant: True if en passant, False otherwise
    :param castle: True if castling, False otherwise
    :return: chess move in algebraic notation
    """
    move_type = "x" if capture else "-"
    enpassant = "e.p." if enpassant else ""
    promotion = "=" + promotion if promotion else ""
    if castle:
        if to_square == 2 or to_square == 58:
            return "O-O-O"
        else:
            return "O-O"

    return (
        FILE[from_square % 8]
        + RANK[from_square // 8]
        + move_type
        + FILE[to_square % 8]
        + RANK[to_square // 8]
        + promotion
        + enpassant
    )


def validate_notation(chess_move: str) -> bool:
    """
    Validate chess move in algebraic notation

    :param chess_move: chess move in algebraic notation
    :return: True if valid, False otherwise
    """
    valid = 1
    debug("validating notation: {}".format(chess_move), 2)
    if chess_move in ["O-O", "O-O-O"]:
        return True

    regex = ure.compile(MOVE_NOTATION_REGEX)
    match = regex.match(chess_move)
    if match:
        if sys.implementation.name != "micropython":
            debug("match: {}".format(match.groups()), 2)
        if match.group(1) is None and match.group(3) and not match.group(2):
            print("pawn push: {}".format(match.group(3)))
            return True
        elif match.group(2) == "x" and match.group(4):
            if match.group(1) and match.group(3):
                return True
        elif (match.group(2) == "" or match.group(2) == "-" or match.group(2) == "x") and not match.group(4):
            if match.group(1) and match.group(3):
                return True
        elif match.group(1) and not match.group(2) and match.group(3):
            return True
        elif match.group(1) and match.group(3) and "=" in chess_move and match.group(4):
            return True
        elif match.group(2) == "x" and match.group(5):
            return True
        elif not match.group(1) or not match.group(3):
            return False
        else:
            return False
    else:
        return False


def parse_move_notation(chess_move: str) -> tuple:
    """
    Parse chess move in algebraic notation

    :param chess_move: chess move in algebraic notation
    :return: tuple of from_square, to_square, capture, promotion, enpassant, castle
    """
    valid = 1
    debug("validating notation: {}".format(chess_move), 2)
    if chess_move in ["O-O", "O-O-O"]:
        castle = "K" if chess_move == "O-O" else "Q"
        return "O", "O", False, None, False, castle

    regex = ure.compile(MOVE_NOTATION_REGEX)
    match = regex.match(chess_move)
    valid_move = False
    if match:
        if sys.implementation.name != "micropython":
            debug("match: {}".format(match.groups()), 2)
        if match.group(1) is None and match.group(3) and not match.group(2):
            valid_move = True
        elif match.group(2) == "x" and match.group(4):
            if match.group(1) and match.group(3):
                valid_move = True
        elif (match.group(2) == "" or match.group(2) == "-" or match.group(2) == "x") and not match.group(4):
            if match.group(1) and match.group(3):
                valid_move = True
        elif match.group(1) and not match.group(2) and match.group(3):
            valid_move = True
        elif match.group(1) and match.group(3) and "=" in chess_move and match.group(4):
            valid_move = True
        elif match.group(2) == "x" and match.group(5):
            valid_move = True
        elif not match.group(1) or not match.group(3):
            valid_move = False
        else:
            valid_move = False

    if valid_move:
        from_square = match.group(1)
        to_square = match.group(3)
        capture = True if match.group(2) == "x" else False
        promotion = match.group(4)[1] if match.group(4) else None
        enpassant = True if match.group(5) else False
        return from_square, to_square, capture, promotion, enpassant, False
    else:
        return None, None, None, None, None, None


def algebraic_to_board_index(algebraic):
    """
    Translate algebraic notation to a board index

    :param algebraic: board index
    :return: board index
    """
    if algebraic in ["O-O", "O-O-O"]:
        return None

    debug("algebraic to board index: {}".format(algebraic), 2)
    return RANK.index(algebraic[1]) * 8 + FILE.index(algebraic[0].lower())


def board_index_to_algebraic(index):
    """
    Translate board index to algebraic notation

    :param index: board index
    :return: algebraic notation
    """
    return FILE[index % 8] + RANK[index // 8]


def check_boundary(index: int, rank: int) -> bool:
    """
    Check if the index is on the given rank

    :param index: board index
    :param rank: rank to check
    :return: True if on the rank, False otherwise
    """
    is_in_bounds = 0 <= index < 64 and index // 8 == rank
    debug("boundary check: index = {}, rank = {}, in bounds = {}".format(index, rank, is_in_bounds), 2)
    return 0 <= index < 64 and index // 8 == rank


def debug(message: str, level: int = 1):
    """
    debug a debug message

    :param message: message to debug if DEBUG is True
    :param level: level of debug message
    :return: None
    """
    if DEBUG >= level:
        print(message)


def get_square_color(square: int) -> int:
    """
    Get the color of a square on the chessboard

    :param square: Square number

    :return: 0 for "light" or 1 for "dark"
    """
    if square < 0 or square > 63:
        raise Exception("square must be between 0 and 63")
    return (square // 8 + square % 8) % 2


def parse_fen(fen: str) -> list:
    """
    Parse a FEN string into a list representing board positions

    :param fen: the FEN string to parse

    :return: list representing board positions
    """
    board = list(" " * 64)
    fen = fen.split()

    i = 8
    for rank in fen[0].split("/"):
        j = 0
        for char in rank:
            if char.isdigit():
                j += int(char)
            else:
                board_index = (i - 1) * 8 + j
                board[board_index] = char
                j += 1
        i -= 1

    return board


class Chess:
    board: list = list(" " * 64)
    turn: str = "w"
    castling: list = list("KQkq")
    enpassant: str = "-"
    halfmove: int = 0
    fullmove: int = 1
    history: list = []
    result: str = "*"  # "*" for game in progress, "1-0" for white win, "0-1" for black win, "1/2-1/2" for draw
    checkmate_flag: bool = False
    stalemate_flag: bool = False
    insufficient_material_flag: bool = False
    check_flag: bool = False
    game_over_flag: bool = False

    def __init__(self, fen: str = None):
        """
        Initialize the game state. If fen is provided, the game state is set
        according to the FEN string. Otherwise, the game state is set to the
        standard starting position.

        :param fen: the FEN string to use to set the game state

        :return: None
        """
        if fen:
            self.set_fen(fen)
        else:
            self.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

    def __str__(self):
        """
        Return a string representation of the board.
        """
        board = self.board
        s = "  +---------------+\n"
        for i in range(56, -1, -8):
            s += str((i // 8) + 1) + " |"
            for j in range(8):
                s += board[i + j] + "|"
            s += "\n"
        s += "  +---------------+\n"
        s += "   a b c d e f g h"
        return s

    def __getitem__(self, index: int):
        """
        Return the character at the given board index.
        """
        return self.board[index]

    def __setitem__(self, index: int, value: str):
        """
        Set the character at the given board index to the given value.
        """
        self.board[index] = value

    def reset_board(self):
        """
        Reset the board to the starting position.

        :return: None
        """
        self.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        self.history = []

    def set_fen(self, fen: str):
        """
        Set the game state according to the given FEN string.

        :param fen: the FEN string to use to set the game state

        :return: None
        """
        fen = fen.split()
        self.board = list(" " * 64)
        self.turn = fen[1]
        self.castling = list(fen[2])
        self.enpassant = fen[3]
        self.halfmove = int(fen[4])
        self.fullmove = int(fen[5])
        self.check_flag = False
        self.checkmate_flag = False
        self.stalemate_flag = False
        self.insufficient_material_flag = False
        self.game_over_flag = False

        i = 8
        for rank in fen[0].split("/"):
            j = 0
            for char in rank:
                if char.isdigit():
                    j += int(char)
                else:
                    board_index = (i - 1) * 8 + j
                    self.board[board_index] = char
                    j += 1
            i -= 1

    def get_fen(self):
        """
        Return the FEN string representing the current game state.

        :return: the FEN string representing the current game state
        """
        fen = ""
        for i in range(56, -1, -8):
            empty = 0
            for j in range(8):
                if self.board[i + j] == " ":
                    empty += 1
                else:
                    if empty > 0:
                        fen += str(empty)
                        empty = 0
                    fen += self.board[i + j]
            if empty > 0:
                fen += str(empty)
            if i > 0:
                fen += "/"
        fen += " " + self.turn + " " + "".join(self.castling) + " " + self.enpassant
        fen += " " + str(self.halfmove) + " " + str(self.fullmove)
        return fen

    def get_pgn(self, moves: list = None, result: str = "*"):
        """
        Return the PGN string representing the current game state.

        :param moves: list of moves to include in the PGN string
        :param result: result of the game

        :return: the PGN string representing the current game state
        """
        if moves is None:
            moves = self.history
        pgn = '[Event "?"]\n[Site "?"]\n[Date "?"]\n[Round "?"]\n[White "?"]\n[Black "?"]\n'
        pgn += '[Result "{}"]\n\n'.format(result)
        for i in range(len(moves)):
            pgn += str(i + 1) + ". " + str(moves[i][0]) + " " + str(moves[i][1]) + " "
            pgn += moves[i] + " "
        pgn += result
        return pgn

    def get_board(self, board: list = None):
        """
        Return the board.

        :return: the board
        """
        if board is None:
            return self.board
        else:
            s = "  +---------------+\n"
            for i in range(56, -1, -8):
                s += str((i // 8) + 1) + " |"
                for j in range(8):
                    s += board[i + j] + "|"
                s += "\n"
            s += "  +---------------+\n"
            s += "   a b c d e f g h"
            return s

    def get_segoe_chess_board(self, fen=None) -> str:
        """
        Print the chessboard with Segoe chess font

        :param fen: FEN string to print

        :return: String of chessboard using Segoe chess font
        """

        segoe_chess_board = ""

        if fen is None:
            working_board = self.board.copy()
        else:
            working_board = parse_fen(fen)

        for i in range(8, 0, -1):
            if i < 8:
                segoe_chess_board += "\\r"
            segoe_chess_board += chr(SEGOE_CHESS_FONT_RANK[i - 1])
            for j in range(8):
                square = (i - 1) * 8 + j
                square_color = get_square_color(square)
                if working_board[square] == " ":
                    segoe_chess_board += chr(SEGOE_CHESS_FONT_EMPTY[square_color])
                else:
                    piece = SEGOE_CHESS_FONT_PIECES_LIGHT[working_board[square]]
                    if square_color == 1:
                        piece -= SEGOE_CHESS_FONT_PIECES_DARK_OFFSET
                    segoe_chess_board += chr(piece)
        segoe_chess_board += "\\r"
        segoe_chess_board += chr(SEGOE_CHESS_FONT_CORNER)
        for i in range(8):
            segoe_chess_board += chr(SEGOE_CHESS_FONT_FILE[i])

        return segoe_chess_board

    def identify_piece(self, coord: str):
        """
        Identify the piece at the given board coordinate.

        :param coord: board coordinate in algebraic notation

        :return: the piece at the given board coordinate
        """
        index = algebraic_to_board_index(coord)
        return self.board[index]

    def is_enemy(self, index: int, color: str):
        """
        Return True if the piece at the given index is an enemy piece, and
        False otherwise.

        :param index: the board index
        :param color: the color of the piece to check

        :return: True if the piece at the given index is an enemy piece, and
            False otherwise including if the square is empty
        """
        return self.board[index].islower() if color == "w" else self.board[index].isupper()

    def is_friendly(self, index: int, color: str):
        """
        Return True if the piece at the given index is a friendly piece, and
        False otherwise.

        :param index: the board index
        :param color: the color of the piece to check

        :return: True if the piece at the given index is a friendly piece, and
            False otherwise
        """
        return self.board[index].isupper() if color == "w" else self.board[index].islower()

    def update_turn(self, move: str, promoted: bool = False):
        """
        Update the turn to the next player.

        :return: None
        """
        next_turn = "b" if self.turn == "w" else "w"

        self.check_flag = False
        self.checkmate_flag = False
        self.stalemate_flag = False
        self.game_over_flag = False

        if self.is_check(next_turn):
            self.check_flag = True
            if self.is_checkmate(next_turn):
                self.checkmate_flag = True
                self.result = "1-0" if next_turn == "b" else "0-1"
                move += "#"
                self.game_over_flag = True
            else:
                move += "+"
        elif self.is_stalemate(next_turn):
            self.stalemate_flag = True
            self.result = "1/2-1/2"
            move += "="
            self.game_over_flag = True

        if self.turn == "w":
            self.history.append((move, ""))
        else:
            if len(self.history) == 0:
                self.history.append(("", move))
            else:
                self.history[-1] = (self.history[-1][0], move)

        self.turn = next_turn

        if self.turn == "w":
            self.fullmove += 1
        if move == "O-O" or move == "O-O-O":
            self.halfmove += 1
        else:
            if move[2] == "x":
                self.halfmove = 0
            elif self.board[algebraic_to_board_index(move[3:5])] in "Pp" or promoted:
                self.halfmove = 0
                # update enpassant
                from_square = algebraic_to_board_index(move[0:2])
                to_square = algebraic_to_board_index(move[3:5])
                if abs(from_square - to_square) == 16:
                    self.enpassant = board_index_to_algebraic(int((from_square + to_square) / 2))
                else:
                    self.enpassant = "-"
            else:
                self.halfmove += 1

        print("check_flag: {}".format(self.check_flag))
        print("checkmate_flag: {}".format(self.checkmate_flag))
        print("stalemate_flag: {}".format(self.stalemate_flag))

    def get_move_history(self, num_moves: int = 0):
        """
        Return the move history.

        :param num_moves: the number of moves to return

        :return: the move history
        """
        if num_moves == 0:
            return self.history
        else:
            return self.history[-num_moves:]

    def is_enpassant(self, move: str):
        """
        Return True if the move is an en passant capture, and False otherwise.

        :param move: the move to check

        :return: True if the move is an en passant capture, and False otherwise
        """
        if self.enpassant == "-":
            return False

        if move in ["O-O", "O-O-O"]:
            return False

        index = algebraic_to_board_index(move[:2])
        enpassant = algebraic_to_board_index(self.enpassant)
        piece = self.board[index]
        side = "w" if piece.isupper() else "b"

        if piece not in "Pp":
            return False
        if side == "w" and self.board[enpassant - 8] != "p":
            return False
        elif side == "b" and self.board[enpassant + 8] != "P":
            return False
        return self.enpassant == move[3:5]

    def is_promotion(self, move: str):
        """
        Return True if the move is a promotion, and False otherwise.

        :param move: the move to check

        :return: True if the move is a promotion, and False otherwise
        """

        if move in ["O-O", "O-O-O"]:
            return False

        regex = ure.compile(r"([a-h][1-8])([-x]?)([a-h][1-8])(=?[NBRQnbrq])?(e\.p\.)?")
        match = regex.match(move)
        from_square = algebraic_to_board_index(match.group(1))

        piece = self.board[from_square]
        side = "w" if piece.isupper() else "b"

        if piece not in "Pp":
            return False
        if side == "b" and match.group(3) in "a1b1c1d1e1f1g1h1":
            return True
        elif side == "w" and match.group(3) in "a8b8c8d8e8f8g8h8":
            return True
        return False

    def make_test_move(self, board: list, move: str, side: str = "w"):
        """
        Make a move on the board without checking if it is valid

        :param board: chess board
        :param move: chess move in algebraic notation
        :param side: side to move
        :return: None
        """

        if move in ["O-O", "O-O-O"]:
            self.perform_castle(move, board=board, side=side)

        if self.is_enpassant(move):
            debug("move is enpassant")
            from_square = algebraic_to_board_index(move[0:2])
            to_square = algebraic_to_board_index(move[3:5])
            board[from_square] = " "
            board[to_square] = "P" if side == "w" else "p"
            captured_square = (
                algebraic_to_board_index(self.enpassant) - 8
                if side == "w"
                else algebraic_to_board_index(self.enpassant) + 8
            )
            board[captured_square] = " "
            debug("enpassant move is complete")
            return True

        from_square = algebraic_to_board_index(move[:2])
        to_square = algebraic_to_board_index(move[3:5])

        piece = board[from_square]
        side = "w" if piece.isupper() else "b"

        board[from_square] = " "
        board[to_square] = piece

    def perform_castle(self, move: str, board: list = None, side: str = None):
        """
        Perform a castle move.

        :param move: the castle move
        :param board: the board to perform the move on
        :param side: the side to perform the move on

        :return: None
        """
        if board is None:
            board = self.board

        if side is None:
            side = self.turn

        index = board.index("K" if side == "w" else "k")
        debug("make a castle move: " + move)
        if move == "O-O" and side == "w":
            board[6] = "K"
            board[5] = "R"
            board[4] = " "
            board[7] = " "
            self.castling.remove("K")
            self.castling.remove("Q")
        elif move == "O-O" and side == "b":
            board[62] = "k"
            board[61] = "r"
            board[60] = " "
            board[63] = " "
            self.castling.remove("k")
            self.castling.remove("q")
        elif move == "O-O-O" and side == "w":
            board[2] = "K"
            board[3] = "R"
            board[4] = " "
            board[0] = " "
            self.castling.remove("K")
            self.castling.remove("Q")
        elif move == "O-O-O" and side == "b":
            board[58] = "k"
            board[59] = "r"
            board[60] = " "
            board[56] = " "
            self.castling.remove("k")
            self.castling.remove("q")

    def perform_promotion(self, move: str, board: list = None, side: str = None):
        """
        Perform a promotion move.

        :param move: the promotion move
        :param board: the board to perform the move on
        :param side: the side to perform the move on

        :return: True if promotion is successful, and False otherwise
        """
        if board is None:
            board = self.board

        if side is None:
            side = self.turn

        regex = ure.compile(r"([a-h][1-8])([-x]?)([a-h][1-8])(=?[NBRQnbrq])?(e\.p\.)?")
        match = regex.match(move)
        from_square = algebraic_to_board_index(match.group(1))
        to_square = algebraic_to_board_index(match.group(3))

        piece = board[from_square]
        side = "w" if piece.isupper() else "b"
        if piece not in "Pp":
            return False

        board[from_square] = " "
        board[to_square] = match.group(4)[1].upper() if side == "w" else match.group(4)[1].lower()

    def make_move(self, move: str, side: str = None):
        """
        Make a move on the board, if it is valid

        :param move: chess move in algebraic notation
        :param side: side to move (defaults to self.turn)
        :return: True if move is valid, False otherwise
        """
        if side is None:
            side = self.turn

        if not validate_notation(move):
            return False

        debug("move: {}".format(move))

        if not validate_notation(move):
            return False

        if move not in ["O-O", "O-O-O"]:
            from_square = algebraic_to_board_index(move[:2])
            if (self.board[from_square].isupper() and side != "w") or (
                self.board[from_square].islower() and side != "b"
            ):
                return False

        if self.is_enpassant(move):
            debug("move is enpassant")
            from_square = algebraic_to_board_index(move[0:2])
            to_square = algebraic_to_board_index(move[3:5])
            self.board[from_square] = " "
            self.board[to_square] = "P" if side == "w" else "p"
            captured_square = (
                algebraic_to_board_index(self.enpassant) - 8
                if side == "w"
                else algebraic_to_board_index(self.enpassant) + 8
            )
            self.board[captured_square] = " "
            self.enpassant = "-"
            self.update_turn(move)
            debug("enpassant move is complete")
            return True

        if self.is_promotion(move):
            debug("move is promotion")
            self.perform_promotion(move)
            self.enpassant = "-"
            self.update_turn(move, promoted=True)
            return True

        if self.check_move(move, side):
            debug("move is valid")
            if move != "O-O" and move != "O-O-O":
                debug("move is not castling")
                from_square = algebraic_to_board_index(move[:2])
                to_square = algebraic_to_board_index(move[3:5])
                self.board[to_square] = self.board[from_square]
                self.board[from_square] = " "
                self.enpassant = "-"
                self.update_turn(move)
                debug("move is complete")
                return True
            else:
                self.perform_castle(move)
                self.enpassant = "-"
                self.update_turn(move)
                debug("castling complete")
                return True
        debug("move is invalid, move not made")
        debug("still {}'s move".format("white" if self.turn == "w" else "black"))
        return False

    def check_move(self, move: str, side: str = "w"):
        """
        Check if a move is valid

        :param move: chess move in algebraic notation
        :param side: side to move
        :return: True if move is valid, False otherwise
        """
        if move == "O-O":
            return self.check_castle(6 if side == "w" else 62, side)
        elif move == "O-O-O":
            return self.check_castle(2 if side == "w" else 58, side)
        else:
            return self.check_regular_move(move, side)

    def can_king_castle(self, side: str):
        """
        Check if a king can castle

        :param side: side to check
        :return: True if king can castle, False otherwise
        """
        index = self.board.index("K") if side == "w" else self.board.index("k")
        move_list = self.get_legal_moves(index)

        if "O-O" in move_list or "O-O-O" in move_list:
            return True
        return False

    def check_castle(self, index: int, side: str = "w"):
        """
        Check if a castle move is valid

        :param index: index of king
        :param side: side to move
        :return: True if move is valid, False otherwise
        """
        if side == "w":
            if self.board.index("K") != 4:
                return False
            if index == 6:
                if "K" not in self.castling:
                    return False
                if self.board[5] != " " or self.board[6] != " ":
                    return False

                if (
                    self.is_square_attacked(4, side=side)
                    or self.is_square_attacked(5, side=side)
                    or self.is_square_attacked(6, side=side)
                ):
                    return False
            else:
                if "Q" not in self.castling:
                    return False
                if self.board[1] != " " or self.board[2] != " " or self.board[3] != " ":
                    return False
                if (
                    self.is_square_attacked(2, side=side)
                    or self.is_square_attacked(3, side=side)
                    or self.is_square_attacked(4, side=side)
                ):
                    return False
        else:
            if self.board.index("k") != 60:
                return False
            if index == 62:
                if "k" not in self.castling:
                    return False
                if self.board[61] != " " or self.board[62] != " ":
                    return False
                if (
                    self.is_square_attacked(60, side=side)
                    or self.is_square_attacked(61, side=side)
                    or self.is_square_attacked(62, side=side)
                ):
                    return False
            else:
                if "q" not in self.castling:
                    return False
                if self.board[57] != " " or self.board[58] != " " or self.board[59] != " ":
                    return False
                if (
                    self.is_square_attacked(58, side=side)
                    or self.is_square_attacked(59, side=side)
                    or self.is_square_attacked(60, side=side)
                ):
                    return False

        return True

    def check_regular_move(self, move: str, side: str = "w"):
        """
        Check if a regular move is valid

        :param move: chess move in algebraic notation
        :param side: side to move
        :return: True if move is valid, False otherwise
        """
        from_square = algebraic_to_board_index(move[:2])
        to_square = algebraic_to_board_index(move[3:5])
        piece = self.board[from_square]

        legal_moves = self.get_legal_moves(from_square)

        if piece == " ":
            return False
        if move in legal_moves:
            return True

        return False

    def all_legal_moves(self, color: str, shortcut=False) -> list:
        """
        Return a list of all legal moves for the given color.

        :param color: the color to generate legal moves for
        :param shortcut: if True, return as soon as a legal move is found

        :return: a list of legal moves for the given color
        """
        moves = []
        for i in range(64):
            if self.board[i].isupper() and color == "w":
                moves += self.generate_moves(i)
            elif self.board[i].islower() and color == "b":
                moves += self.generate_moves(i)
            if shortcut and len(moves) > 0:
                moves = self.remove_illegal_moves(moves)
                if len(moves) > 0:
                    return moves
        moves = self.remove_illegal_moves(moves)
        return moves

    def get_legal_moves(self, index: int):
        """
        Return a list of legal moves for the piece at the given index.

        :param index: the board index

        :return: a list of legal moves for the piece at the given index
        """
        piece = self.board[index]
        if piece == " ":
            return []
        else:
            moves = self.generate_moves(index)
            moves = self.remove_illegal_moves(moves)
            return moves

    def generate_moves(self, index: int):
        """
        Return a list of legal moves for the piece at the given index.

        :param index: the index of the piece to generate legal moves for

        :return: a list of legal moves for the piece at the given index
        """
        moves = []
        piece = self.board[index]
        if piece in "Pp":
            moves += self.generate_pawn_moves(index)
        elif piece in "Nn":
            moves += self.generate_knight_moves(index)
        elif piece in "Bb":
            moves += self.generate_bishop_moves(index)
        elif piece in "Rr":
            moves += self.generate_rook_moves(index)
        elif piece in "Qq":
            moves += self.generate_queen_moves(index)
        elif piece in "Kk":
            moves += self.generate_king_moves(index)

        return moves

    def generate_pawn_moves(self, index: int):
        """
        Return a list of legal pawn moves for the pawn at the given index.

        :param index: the index of the pawn to generate legal moves for

        :return: a list of legal pawn moves for the pawn at the given index
        """
        debug("Generating pawn moves for index {}".format(index))
        moves = []
        if self.board[index].isupper():
            if self.board[index + 8] == " ":
                if (index + 8) // 8 < 7:
                    moves.append(move_notation(index, index + 8))
                else:
                    for p in PROMOTED_PIECES:
                        moves.append(move_notation(index, index + 8, promotion=p.upper()))
                if index < 16 and self.board[index + 16] == " ":
                    moves.append(move_notation(index, index + 16))
            if check_boundary(index + 9, (index // 8 + 1)) and self.board[index + 9].islower():
                if (index + 9) // 8 < 7:
                    moves.append(move_notation(index, index + 9, capture=True))
                else:
                    for p in PROMOTED_PIECES:
                        moves.append(move_notation(index, index + 9, promotion=p.upper(), capture=True))
            if check_boundary(index + 7, (index // 8 + 1)) and self.board[index + 7].islower():
                if (index + 7) // 8 < 7:
                    moves.append(move_notation(index, index + 7, capture=True))
                else:
                    for p in PROMOTED_PIECES:
                        moves.append(move_notation(index, index + 7, promotion=p.upper(), capture=True))
            if (
                index % 8 > 0
                and self.board[index - 1] == "p"
                and self.enpassant == chr(ord("a") + (index % 8) - 1) + "6"
            ):
                moves.append(move_notation(index, index + 7, capture=True, enpassant=True))
            if (
                index % 8 < 7
                and self.board[index + 1] == "p"
                and self.enpassant == chr(ord("a") + (index % 8) + 1) + "6"
            ):
                moves.append(move_notation(index, index + 9, capture=True, enpassant=True))
        else:
            if self.board[index - 8] == " ":
                if (index - 8) // 8 > 0:
                    moves.append(move_notation(index, index - 8))
                else:
                    for p in PROMOTED_PIECES:
                        moves.append(move_notation(index, index - 8, promotion=p.lower()))
                if index > 47 and self.board[index - 16] == " ":
                    moves.append(move_notation(index, index - 16))
            if check_boundary(index - 7, (index // 8) - 1) and self.board[index - 7].isupper():
                if (index - 7) // 8 > 0:
                    moves.append(move_notation(index, index - 7, capture=True))
                else:
                    for p in PROMOTED_PIECES:
                        moves.append(move_notation(index, index - 7, promotion=p.lower(), capture=True))
            if check_boundary(index - 9, (index // 8) - 1) and self.board[index - 9].isupper():
                if (index - 9) // 8 > 0:
                    moves.append(move_notation(index, index - 9, capture=True))
                else:
                    for p in PROMOTED_PIECES:
                        moves.append(move_notation(index, index - 9, promotion=p.lower(), capture=True))
            if (
                index % 8 > 0
                and self.board[index - 1] == "P"
                and self.enpassant == chr(ord("a") + (index % 8) - 1) + "3"
            ):
                moves.append(move_notation(index, index - 9, capture=True, enpassant=True))
            if (
                index % 8 < 7
                and self.board[index + 1] == "P"
                and self.enpassant == chr(ord("a") + (index % 8) + 1) + "3"
            ):
                moves.append(move_notation(index, index - 7, capture=True, enpassant=True))
        return moves

    def generate_knight_moves(self, index: int):
        """
        Return a list of legal knight moves for the knight at the given index.

        :param index: the index of the knight to generate legal moves for

        :return: a list of legal knight moves for the knight at the given index
        """
        moves = []
        side = "w" if self.board[index].isupper() else "b"

        if index % 8 > 0:
            if index > 15 and (self.board[index - 15] == " " or self.is_enemy(index - 15, side)):
                moves.append(move_notation(index, index - 15, capture=self.is_enemy(index - 15, side)))
            if index % 8 < 6 and index > 7 and (self.board[index - 6] == " " or self.is_enemy(index - 6, side)):
                moves.append(move_notation(index, index - 6, capture=self.is_enemy(index - 6, side)))
            if index % 8 < 7 and index < 48 and (self.board[index + 17] == " " or self.is_enemy(index + 17, side)):
                moves.append(move_notation(index, index + 17, capture=self.is_enemy(index + 17, side)))
            if index % 8 < 6 and index < 56 and (self.board[index + 10] == " " or self.is_enemy(index + 10, side)):
                moves.append(move_notation(index, index + 10, capture=self.is_enemy(index + 10, side)))
        if index % 8 < 7:
            if index % 8 > 0 and index > 16 and (self.board[index - 17] == " " or self.is_enemy(index - 17, side)):
                moves.append(move_notation(index, index - 17, capture=self.is_enemy(index - 17, side)))
            if index % 8 > 1 and index > 7 and (self.board[index - 10] == " " or self.is_enemy(index - 10, side)):
                moves.append(move_notation(index, index - 10, capture=self.is_enemy(index - 10, side)))
            if index % 8 > 0 and index < 48 and (self.board[index + 15] == " " or self.is_enemy(index + 15, side)):
                moves.append(move_notation(index, index + 15, capture=self.is_enemy(index + 15, side)))
            if index % 8 > 1 and index < 56 and (self.board[index + 6] == " " or self.is_enemy(index + 6, side)):
                moves.append(move_notation(index, index + 6, capture=self.is_enemy(index + 6, side)))
        if index % 8 == 0:
            if index > 15 and (self.board[index - 15] == " " or self.is_enemy(index - 15, side)):
                moves.append(move_notation(index, index - 15, capture=self.is_enemy(index - 15, side)))
            if index > 7 and (self.board[index - 6] == " " or self.is_enemy(index - 6, side)):
                moves.append(move_notation(index, index - 6, capture=self.is_enemy(index - 6, side)))
            if index < 48 and (self.board[index + 17] == " " or self.is_enemy(index + 17, side)):
                moves.append(move_notation(index, index + 17, capture=self.is_enemy(index + 17, side)))
            if index < 56 and (self.board[index + 10] == " " or self.is_enemy(index + 10, side)):
                moves.append(move_notation(index, index + 10, capture=self.is_enemy(index + 10, side)))
        if index % 8 == 7:
            if index > 16 and (self.board[index - 17] == " " or self.is_enemy(index - 17, side)):
                moves.append(move_notation(index, index - 17, capture=self.is_enemy(index - 17, side)))
            if index > 7 and (self.board[index - 10] == " " or self.is_enemy(index - 10, side)):
                moves.append(move_notation(index, index - 10, capture=self.is_enemy(index - 10, side)))
            if index < 48 and (self.board[index + 15] == " " or self.is_enemy(index + 15, side)):
                moves.append(move_notation(index, index + 15, capture=self.is_enemy(index + 15, side)))
            if index < 56 and (self.board[index + 6] == " " or self.is_enemy(index + 6, side)):
                moves.append(move_notation(index, index + 6, capture=self.is_enemy(index + 6, side)))
        return moves

    def generate_bishop_moves(self, index: int):
        """
        Return a list of legal bishop moves for the bishop at the given index.

        :param index: the index of the bishop to generate legal moves for

        :return: a list of legal bishop moves for the bishop at the given index
        """
        moves = []
        side = "w" if self.board[index].isupper() else "b"

        # up right diagonal
        for i, rank in enumerate(range((index // 8) + 1, 8), start=1):
            if (index + 9 * i) < 8 * (rank + 1):
                if self.board[index + 9 * i] == " ":
                    moves.append(move_notation(index, index + 9 * i))
                elif self.is_enemy(index + 9 * i, side):
                    moves.append(move_notation(index, index + 9 * i, capture=True))
                    break
                else:
                    break
            else:
                break

        # up left diagonal
        for i, rank in enumerate(range((index // 8) + 1, 8), start=1):
            if (index + 7 * i) > 8 * rank - 1:
                if self.board[index + 7 * i] == " ":
                    moves.append(move_notation(index, index + 7 * i))
                elif self.is_enemy(index + 7 * i, side):
                    moves.append(move_notation(index, index + 7 * i, capture=True))
                    break
                else:
                    break
            else:
                break

        # down right diagonal
        for i, rank in enumerate(range((index // 8) - 1, -1, -1), start=1):
            if (index - 7 * i) < 8 * (rank + 1):
                if self.board[index - 7 * i] == " ":
                    moves.append(move_notation(index, index - 7 * i))
                elif self.is_enemy(index - 7 * i, side):
                    moves.append(move_notation(index, index - 7 * i, capture=True))
                    break
                else:
                    break
            else:
                break

        # down left diagonal
        for i, rank in enumerate(range((index // 8) - 1, -1, -1), start=1):
            if (index - 9 * i) > 8 * rank - 1:
                if self.board[index - 9 * i] == " ":
                    moves.append(move_notation(index, index - 9 * i))
                elif self.is_enemy(index - 9 * i, side):
                    moves.append(move_notation(index, index - 9 * i, capture=True))
                    break
                else:
                    break
            else:
                break

        return moves

    def generate_rook_moves(self, index: int):
        """
        Return a list of legal rook moves for the rook at the given index.

        :param index: the index of the rook to generate legal moves for

        :return: a list of legal rook moves for the rook at the given index
        """
        moves = []
        side = "w" if self.board[index].isupper() else "b"

        # up
        for i, rank in enumerate(range((index // 8) + 1, 8), start=1):
            if self.board[index + 8 * i] == " ":
                moves.append(move_notation(index, index + 8 * i))
            elif self.is_enemy(index + 8 * i, side):
                moves.append(move_notation(index, index + 8 * i, capture=True))
                break
            else:
                break

        # down
        for i, rank in enumerate(range((index // 8), 0, -1), start=1):
            if self.board[index - 8 * i] == " ":
                moves.append(move_notation(index, index - 8 * i))
            elif self.is_enemy(index - 8 * i, side):
                moves.append(move_notation(index, index - 8 * i, capture=True))
                break
            else:
                break

        # right
        for i, file in enumerate(range((index % 8) + 1, 8), start=1):
            if self.board[index + i] == " ":
                moves.append(move_notation(index, index + i))
            elif self.is_enemy(index + i, side):
                moves.append(move_notation(index, index + i, capture=True))
                break
            else:
                break

        # left
        for i, file in enumerate(range((index % 8), 0, -1), start=1):
            if self.board[index - i] == " ":
                moves.append(move_notation(index, index - i))
            elif self.is_enemy(index - i, side):
                moves.append(move_notation(index, index - i, capture=True))
                break
            else:
                break

        return moves

    def generate_queen_moves(self, index: int):
        """
        Return a list of legal queen moves for the queen at the given index.

        :param index: the index of the queen to generate legal moves for

        :return: a list of legal queen moves for the queen at the given index
        """
        return self.generate_bishop_moves(index) + self.generate_rook_moves(index)

    def generate_king_moves(self, index: int):
        """
        Return a list of legal king moves for the king at the given index.

        :param index: the index of the king to generate legal moves for

        :return: a list of legal king moves for the king at the given index
        """
        moves = []
        side = "w" if self.board[index].isupper() else "b"

        # up
        if index < 56 and (self.board[index + 8] == " " or self.is_enemy(index + 8, side)):
            moves.append(move_notation(index, index + 8, capture=self.is_enemy(index + 8, side)))

        # down
        if index > 7 and (self.board[index - 8] == " " or self.is_enemy(index - 8, side)):
            moves.append(move_notation(index, index - 8, capture=self.is_enemy(index - 8, side)))

        # right
        if (index + 1) % 8 != 0 and (self.board[index + 1] == " " or self.is_enemy(index + 1, side)):
            moves.append(move_notation(index, index + 1, capture=self.is_enemy(index + 1, side)))

        # left
        if index % 8 != 0 and (self.board[index - 1] == " " or self.is_enemy(index - 1, side)):
            moves.append(move_notation(index, index - 1, capture=self.is_enemy(index - 1, side)))

        # up right
        if (index + 1) % 8 != 0 and index < 56 and (self.board[index + 9] == " " or self.is_enemy(index + 9, side)):
            moves.append(move_notation(index, index + 9, capture=self.is_enemy(index + 9, side)))

        # up left
        if index % 8 != 0 and index < 56 and (self.board[index + 7] == " " or self.is_enemy(index + 7, side)):
            moves.append(move_notation(index, index + 7, capture=self.is_enemy(index + 7, side)))

        # down right
        if (index + 1) % 8 != 0 and index > 7 and (self.board[index - 7] == " " or self.is_enemy(index - 7, side)):
            moves.append(move_notation(index, index - 7, capture=self.is_enemy(index - 7, side)))

        # down left
        if index % 8 != 0 and index > 7 and (self.board[index - 9] == " " or self.is_enemy(index - 9, side)):
            moves.append(move_notation(index, index - 9, capture=self.is_enemy(index - 9, side)))

        # king side castle
        if side == "w":
            if self.check_castle(6, side):
                moves.append("O-O")
        else:
            if self.check_castle(62, side):
                moves.append("O-O")

        # queen side castle
        if side == "w":
            if self.check_castle(2, side):
                moves.append("O-O-O")
        else:
            if self.check_castle(58, side):
                moves.append("O-O-O")

        return moves

    def is_square_attacked(self, index: int, board: list = None, side: str = None):
        """
        Return True if the given square is under attack by the enemy, False otherwise.

        :param index: the index of the square to check
        :param board: the board to check for attacks
        :param side: the side to check for attacks

        :return: True if the given square is under attack by the enemy, False otherwise
        """
        if board is None:
            board = self.board

        if side is None:
            side = "w" if board[index].isupper() else "b"

        debug("-----------------")
        debug("Checking if square {} is attacked".format(index))
        debug("friendly side:  {}".format(side))

        debug(self.get_board(board), 2)
        # check for pawns
        debug("Checking for pawns attacks", 2)
        if side == "w":
            if index % 8 != 0 and index > 7 and board[index + 9] == "p":
                debug("black pawn attack: {}".format(index + 9))
                return True
            if (index + 1) % 8 != 0 and index > 7 and board[index + 7] == "p":
                debug("black pawn attack: {}".format(index + 7))
                return True
        else:
            if index % 8 != 0 and index < 56 and board[index - 7] == "P":
                debug("white pawn attack: {}".format(index - 7))
                return True
            if (index + 1) % 8 != 0 and index < 56 and board[index - 9] == "P":
                debug("white pawn attack: {}".format(index - 9))
                return True

        # check for knights
        debug("checking for knights attacks", 2)
        rank_orign = index // 8
        rank_idx = [-2, -2, -1, -1, 1, 1, 2, 2]
        for j, i in enumerate([-17, -15, -10, -6, 6, 10, 15, 17]):
            rank = rank_orign + rank_idx[j]
            if check_boundary(index + i, rank):
                if 0 <= index + i < 64 and board[index + i] == ("n" if side == "w" else "N"):
                    debug("knight attack: {}".format(index + i))
                    return True

        # check for bishops and queens
        debug("checking for bishops and queens attacks", 2)
        for i in [-9, -7, 7, 9]:
            rank = index // 8
            for j in range(1, 8):
                if i < 0:
                    rank -= 1
                else:
                    rank += 1
                if 0 <= index + i * j < 64 and check_boundary(index + i * j, rank):
                    debug("checking bishop/queen attack: {}".format(index + i * j), 2)
                    if board[index + i * j] == ("b" if side == "w" else "B") or board[index + i * j] == (
                        "q" if side == "w" else "Q"
                    ):
                        debug("bishop/queen attack: {}".format(index + i * j))
                        return True
                    if board[index + i * j] != " ":
                        debug("bishop/queen attack blocked: {}".format(index + i * j))
                        break
                else:
                    break

        # check for rooks and queens
        debug("checking for rooks and queens attacks", 2)
        for i in [-8, -1, 1, 8]:
            rank = index // 8
            for j in range(1, 8):
                if i == -8:
                    rank -= 1
                elif i == 8:
                    rank += 1
                if 0 <= index + i * j < 64 and check_boundary(index + i * j, rank):
                    debug("checking rook/queen attack: {}".format(index + i * j), 2)
                    if board[index + i * j] == ("r" if side == "w" else "R") or board[index + i * j] == (
                        "q" if side == "w" else "Q"
                    ):
                        debug("rook/queen attack: {}".format(index + i * j))
                        return True
                    if board[index + i * j] != " ":
                        debug("rook/queen attack blocked: {}".format(index + i * j))
                        break
                else:
                    break

        # check for kings
        debug("checking for king attacks", 2)
        for i in [-9, -8, -7, -1, 1, 7, 8, 9]:
            if 0 <= index + i < 64 and board[index + i] == ("k" if side == "w" else "K"):
                debug("king attack: {}".format(index + i))
                return True

        debug("no attack")
        return False

    def remove_illegal_moves(self, moves: list):
        """
        Remove moves that leave the king in check.

        :param moves: a list of moves to remove illegal moves from

        :return: a list of legal moves
        """
        legal_moves = []
        for move in moves:
            if not self.is_move_in_check(move):
                legal_moves.append(move)
        return legal_moves

    def is_move_in_check(self, move: str):
        """
        Return True if the given move leaves the king of the given side in check.

        :param move: the move to check

        :return: True if the given move leaves the king of the given side in check
        """
        debug("Checking if move {} leaves king in check".format(move))

        if move == "O-O" or move == "O-O-O":
            return False
        moved_piece = algebraic_to_board_index(move[:2])
        side = "w" if self.board[moved_piece].isupper() else "b"
        king_piece = "K" if side == "w" else "k"

        previous_board = self.board.copy()
        self.make_test_move(previous_board, move, side)
        king_index = previous_board.index(king_piece)
        return self.is_square_attacked(king_index, previous_board)

    def is_check(self, side: str):
        """
        Return True if the given side is in check, False otherwise.

        :param side: the side to check

        :return: True if the given side is in check, False otherwise
        """
        debug("Checking if {} is in check".format(side))

        king_piece = "K" if side == "w" else "k"
        king_index = self.board.index(king_piece)
        return self.is_square_attacked(king_index)

    def is_checkmate(self, side: str):
        """
        Return True if the given side is in checkmate, False otherwise.

        :param side: the side to check

        :return: True if the given side is in checkmate, False otherwise
        """
        debug("Checking if {} is in checkmate".format(side))

        if not self.is_check(side):
            return False

        moves = self.all_legal_moves(side)
        return len(moves) == 0

    def is_stalemate(self, side: str):
        """
        Return True if the given side is in stalemate, False otherwise.

        :param side: the side to check

        :return: True if the given side is in stalemate, False otherwise
        """
        debug("Checking if {} is in stalemate".format(side))

        if self.is_check(side):
            return False

        moves = self.all_legal_moves(side, shortcut=True)
        debug("moves: {}".format(moves))
        return len(moves) == 0
