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
    move(self, move) - make the given move if it is valid. The move should
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

RANK = ["1", "2", "3", "4", "5", "6", "7", "8"]
FILE = ["a", "b", "c", "d", "e", "f", "g", "h"]


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


def algebraic_to_board_index(algebraic):
    """
    Translate algebraic notation to a board index

    :param algebraic: board index
    :return: board index
    """
    return RANK.index(algebraic[1]) * 8 + FILE.index(algebraic[0].lower())


def make_test_move(board: list, chess_move: str):
    """
    Make a move on the board without checking if it is valid

    :param board: chess board
    :param chess_move: chess move in algebraic notation
    :return: None
    """
    from_square = algebraic_to_board_index(chess_move[:2])
    to_square = algebraic_to_board_index(chess_move[3:5])
    piece = board[from_square]
    board[from_square] = " "
    board[to_square] = piece


def check_boundary(index: int, rank: int) -> bool:
    """
    Check if the index is on the given rank

    :param index: board index
    :param rank: rank to check
    :return: True if on the rank, False otherwise
    """
    is_in_bounds = 0 <= index < 64 and index // 8 == rank
    print("boundary check: index = {}, rank = {}, in bounds = {}".format(index, rank, is_in_bounds))
    return 0 <= index < 64 and index // 8 == rank


class Chess:
    board: list = list(" " * 64)
    turn: str = "w"
    castling: list = list("KQkq")
    enpassant: str = "-"
    halfmove: int = 0
    fullmove: int = 1

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

    def make_move(self, move: str):
        """
        Make a move on the board, if it is valid

        :param move: chess move in algebraic notation
        :return: True if move is valid, False otherwise
        """
        from_square = algebraic_to_board_index(move[:2])
        to_square = algebraic_to_board_index(move[3:5])
        if self.check_move(move, side=self.turn):
            self.board[to_square] = self.board[from_square]
            self.board[from_square] = " "
            self.turn = "b" if self.turn == "w" else "w"
            return True
        return False

    def check_move(self, move: str, side: str="w"):
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

    def check_castle(self, index: int, side: str="w"):
        """
        Check if a castle move is valid

        :param index: index of king
        :param side: side to move
        :return: True if move is valid, False otherwise
        """
        if self.board[index] != "K" if side == "w" else "k":
            return False
        if side == "w":
            if index == 6:
                if "K" not in self.castling:
                    return False
                if self.board[5] != " " or self.board[6] != " ":
                    return False
                if self.is_attacked(4, "b") or self.is_attacked(5, "b") or self.is_attacked(6, "b"):
                    return False
            else:
                if "Q" not in self.castling:
                    return False
                if self.board[1] != " " or self.board[2] != " " or self.board[3] != " ":
                    return False
                if self.is_attacked(2, "b") or self.is_attacked(3, "b") or self.is_attacked(4, "b"):
                    return False
        else:
            if index == 62:
                if "k" not in self.castling:
                    return False
                if self.board[61] != " " or self.board[62] != " ":
                    return False
                if self.is_attacked(60, "w") or self.is_attacked(61, "w") or self.is_attacked(62, "w"):
                    return False
            else:
                if "q" not in self.castling:
                    return False
                if self.board[57] != " " or self.board[58] != " " or self.board[59] != " ":
                    return False
                if self.is_attacked(58, "w") or self.is_attacked(59, "w") or self.is_attacked(60, "w"):
                    return False
        return True

    def check_regular_move(self, move: str, side: str="w"):
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

    def all_legal_moves(self, color: str):
        """
        Return a list of all legal moves for the given color.

        :param color: the color to generate legal moves for

        :return: a list of legal moves for the given color
        """
        moves = []
        for i in range(64):
            if self.board[i].isupper() and color == "w":
                moves += self.generate_moves(i)
            elif self.board[i].islower() and color == "b":
                moves += self.generate_moves(i)
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
        moves = []
        if self.board[index].isupper():
            if self.board[index + 8] == " ":
                moves.append(move_notation(index, index + 8))
                if index < 16 and self.board[index + 16] == " ":
                    moves.append(move_notation(index, index + 16))
            if self.board[index + 7].islower():
                moves.append(move_notation(index, index + 7, capture=True))
            if self.board[index + 9].islower():
                moves.append(move_notation(index, index + 9, capture=True))
            if (
                index % 8 > 0
                and self.board[index + 7] == "p"
                and self.enpassant == chr(ord("a") + (index % 8) - 1) + "6"
            ):
                moves.append(move_notation(index, index + 7, capture=True, enpassant=True))
            if (
                index % 8 < 7
                and self.board[index + 9] == "p"
                and self.enpassant == chr(ord("a") + (index % 8) + 1) + "6"
            ):
                moves.append(move_notation(index, index + 9))
        else:
            if self.board[index - 8] == " ":
                moves.append(move_notation(index, index - 8))
                if index > 47 and self.board[index - 16] == " ":
                    moves.append(move_notation(index, index - 16))
            if self.board[index - 7].isupper():
                moves.append(move_notation(index, index - 7))
            if self.board[index - 9].isupper():
                moves.append(move_notation(index, index - 9))
            if (
                index % 8 > 0
                and self.board[index - 9] == "P"
                and self.enpassant == chr(ord("a") + (index % 8) - 1) + "3"
            ):
                moves.append(move_notation(index, index - 9))
            if (
                index % 8 < 7
                and self.board[index - 7] == "P"
                and self.enpassant == chr(ord("a") + (index % 8) + 1) + "3"
            ):
                moves.append(move_notation(index, index - 7))
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
            if index > 7 and (self.board[index - 6] == " " or self.is_enemy(index - 6, side)):
                moves.append(move_notation(index, index - 6, capture=self.is_enemy(index - 6, side)))
            if index < 48 and (self.board[index + 17] == " " or self.is_enemy(index + 17, side)):
                moves.append(move_notation(index, index + 17, capture=self.is_enemy(index + 17, side)))
            if index < 56 and (self.board[index + 10] == " " or self.is_enemy(index + 10, side)):
                moves.append(move_notation(index, index + 10, capture=self.is_enemy(index + 10, side)))
        if index % 8 < 7:
            if index > 16 and (self.board[index - 17] == " " or self.is_enemy(index - 17, side)):
                moves.append(move_notation(index, index - 17, capture=self.is_enemy(index - 17, side)))
            if index > 7 and (self.board[index - 10] == " " or self.is_enemy(index - 10, side)):
                moves.append(move_notation(index, index - 10, capture=self.is_enemy(index - 10, side)))
            if index < 48 and (self.board[index + 15] == " " or self.is_enemy(index + 15, side)):
                moves.append(move_notation(index, index + 15, capture=self.is_enemy(index + 15, side)))
            if index < 56 and (self.board[index + 6] == " " or self.is_enemy(index + 6, side)):
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

        return moves

    def is_square_attacked(self, index: int, board: list = None):
        """
        Return True if the given square is under attack by the enemy, False otherwise.

        :param index: the index of the square to check
        :param board: the board to check for attacks

        :return: True if the given square is under attack by the enemy, False otherwise
        """
        side = "w" if board[index].isupper() else "b"
        if board is None:
            board = self.board

        print("-----------------")
        print("Checking if square {} is attacked".format(index))
        print("piece color:  {}".format(side))

        print(self.get_board(board))
        # check for pawns
        print("Checking for pawns attacks")
        if side == "w":
            if index % 8 != 0 and index > 7 and board[index - 9] == "p":
                print("pawn attack: {}".format(index - 9))
                return True
            if (index + 1) % 8 != 0 and index > 7 and board[index - 7] == "p":
                print("pawn attack: {}".format(index - 7))
                return True
        else:
            if index % 8 != 0 and index < 56 and board[index + 7] == "P":
                print("pawn attack: {}".format(index + 7))
                return True
            if (index + 1) % 8 != 0 and index < 56 and board[index + 9] == "P":
                print("pawn attack: {}".format(index + 9))
                return True

        # check for knights
        print("checking for knights attacks")
        rank_orign = (index // 8)
        rank_idx = [-2, -2, -1, -1, 1, 1, 2, 2]
        for j, i in enumerate([-17, -15, -10, -6, 6, 10, 15, 17]):
            rank = rank_orign + rank_idx[j]
            if check_boundary(index + i, rank):
                if 0 <= index + i < 64 and board[index + i] == ("n" if side == "w" else "N"):
                    print("knight attack: {}".format(index + i))
                    return True

        # check for bishops and queens
        print("checking for bishops and queens attacks")
        for i in [-9, -7, 7, 9]:
            rank = index // 8
            for j in range(1, 8):
                if i < 0:
                    rank -= 1
                else:
                    rank += 1
                if 0 <= index + i * j < 64 and check_boundary(index + i * j, rank):
                    print("checking bishop/queen attack: {}".format(index + i * j))
                    if board[index + i * j] == ("b" if side == "w" else "B") or board[index + i * j] == ("q" if side == "w" else "Q"):
                        print("bishop/queen attack: {}".format(index + i * j))
                        return True
                    if board[index + i * j] != " ":
                        print("bishop/queen attack blocked: {}".format(index + i * j))
                        break
                else:
                    break

        # check for rooks and queens
        print("checking for rooks and queens attacks")
        for i in [-8, -1, 1, 8]:
            rank = index // 8
            for j in range(1, 8):
                if i == -8:
                    rank -= 1
                elif i == 8:
                    rank += 1
                if 0 <= index + i * j < 64 and check_boundary(index + i * j, rank):
                    print("checking rook/queen attack: {}".format(index + i * j))
                    if board[index + i * j] == ("r" if side == "w" else "R") or board[index + i * j] == ("q" if side == "w" else "Q"):
                        print("rook/queen attack: {}".format(index + i * j))
                        return True
                    if board[index + i * j] != " ":
                        print("rook/queen attack blocked: {}".format(index + i * j))
                        break
                else:
                    break

        # check for kings
        print("checking for king attacks")
        for i in [-9, -8, -7, -1, 1, 7, 8, 9]:
            if 0 <= index + i < 64 and board[index + i] == ("k" if side == "w" else "K"):
                print("king attack: {}".format(index + i))
                return True

        print("no attack")
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
        moved_piece = algebraic_to_board_index(move[:2])
        side = "w" if self.board[moved_piece].isupper() else "b"
        king_piece = "K" if side == "w" else "k"

        previous_board = self.board.copy()
        make_test_move(previous_board, move)
        # print(self.get_board(previous_board))
        king_index = previous_board.index(king_piece)
        return self.is_square_attacked(king_index, previous_board)


