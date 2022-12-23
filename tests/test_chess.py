import chess
from pytest_unordered import unordered
from pytest_check import check


board = chess.Chess()


def test_initial_board():
    assert board.get_board() == ["R", "N", "B", "Q", "K", "B", "N", "R",
                                 "P", "P", "P", "P", "P", "P", "P", "P",
                                 " ", " ", " ", " ", " ", " ", " ", " ",
                                 " ", " ", " ", " ", " ", " ", " ", " ",
                                 " ", " ", " ", " ", " ", " ", " ", " ",
                                 " ", " ", " ", " ", " ", " ", " ", " ",
                                 "p", "p", "p", "p", "p", "p", "p", "p",
                                 "r", "n", "b", "q", "k", "b", "n", "r"]


def test_initial_board_fen():
    board.set_fen("r6r/1b2k1bq/8/8/7B/8/8/R3K2R b KQ - 3 2")
    assert board.get_fen() == "r6r/1b2k1bq/8/8/7B/8/8/R3K2R b KQ - 3 2"
    assert board.get_board() == ["R", " ", " ", " ", "K", " ", " ", "R",
                                 " ", " ", " ", " ", " ", " ", " ", " ",
                                 " ", " ", " ", " ", " ", " ", " ", " ",
                                 " ", " ", " ", " ", " ", " ", " ", "B",
                                 " ", " ", " ", " ", " ", " ", " ", " ",
                                 " ", " ", " ", " ", " ", " ", " ", " ",
                                 " ", "b", " ", " ", "k", " ", "b", "q",
                                 "r", " ", " ", " ", " ", " ", " ", "r"]


def test_check_move_notation():
    with check:
        assert chess.validate_notation("e4") is True
    with check:
        assert chess.validate_notation("e4e5") is True
    with check:
        assert chess.validate_notation("e4-e5") is True
    with check:
        assert chess.validate_notation("e4xe5") is True
    with check:
        assert chess.validate_notation("e4xe5=Q") is True
    with check:
        assert chess.validate_notation("e9a2") is False


def test_parse_move_notation():
    with check:
        assert chess.parse_move_notation("e4") == (None, "e4", False, None, False, False)
    with check:
        assert chess.parse_move_notation("h1-g1") == ("h1", "g1", False, None, False, False)
    with check:
        assert chess.parse_move_notation("h1xg1") == ("h1", "g1", True, None, False, False)
    with check:
        assert chess.parse_move_notation("h1-g1=Q") == ("h1", "g1", False, "Q", False, False)
    with check:
        assert chess.parse_move_notation("h1xg1=Q") == ("h1", "g1", True, "Q", False, False)
    with check:
        assert chess.parse_move_notation("O-O") == ("O", "O", False, None, False, "K")
    with check:
        assert chess.parse_move_notation("O-O-O") == ("O", "O", False, None, False, "Q")
    with check:
        assert chess.parse_move_notation("g4xf3e.p.") == ("g4", "f3", True, None, True, False)


def test_board_index():
    with check:
        assert chess.algebraic_to_board_index("a1") == 0
    with check:
        assert chess.algebraic_to_board_index("d5") == 35
    with check:
        assert chess.algebraic_to_board_index("h8") == 63


def test_board_algebraic():
    with check:
        assert chess.board_index_to_algebraic(0) == "a1"
    with check:
        assert chess.board_index_to_algebraic(35) == "d5"
    with check:
        assert chess.board_index_to_algebraic(63) == "h8"


def test_is_check():
    board.set_fen("4k3/8/3N4/8/8/8/8/4K3 b - - 0 1")
    with check:
        assert board.is_check("b") is True and board.is_checkmate("b") is False
        assert board.is_check("w") is False

    board.set_fen("5nrN/7k/5BB1/3KP1P1/4p3/8/6b1/7R b - - 0 1")
    with check:
        assert board.is_check("b") is True and board.is_checkmate("b") is True
        assert board.is_check("w") is False

    board.set_fen("1k3nrN/8/2p2BB1/3KP1P1/8/8/4b3/7R w - - 0 1")
    with check:
        assert board.is_check("b") is False
        assert board.is_check("w") is True and board.is_checkmate("w") is False


def test_legal_knight_moves():
    board.set_fen("4k3/8/8/8/8/3N4/8/4K3 b - - 0 1")
    index = chess.algebraic_to_board_index("d3")
    with check:
        assert board.get_legal_moves(index) == unordered(
            ["d3-c1", "d3-c5", "d3-e5", "d3-f2", "d3-f4", "d3-b2", "d3-b4"]
        )

    board.set_fen("4k3/8/8/N7/8/8/8/4K3 b - - 0 1")
    index = chess.algebraic_to_board_index("a5")
    with check:
        assert board.get_legal_moves(index) == unordered(["a5-b3", "a5-c4", "a5-b7", "a5-c6"])

    board.set_fen("4k3/8/8/8/8/8/8/N3K3 w - - 0 1")
    index = chess.algebraic_to_board_index("a1")
    with check:
        assert board.get_legal_moves(index) == unordered(["a1-b3", "a1-c2"])

    board.set_fen("4k3/8/3N4/8/8/8/8/4K3 w - - 0 1")
    index = chess.algebraic_to_board_index("d6")
    with check:
        assert board.is_check("b") is True
        assert board.get_legal_moves(index) == unordered(
            ["d6-c4", "d6-e4", "d6-f5", "d6-f7", "d6-c8", "d6xe8", "d6-b5", "d6-b7"]
        )

    board.set_fen("4k3/8/8/8/8/8/8/1N2K3 w - - 0 1")
    index = chess.algebraic_to_board_index("b1")
    with check:
        assert board.get_legal_moves(index) == unordered(["b1-a3", "b1-c3", "b1-d2"])

    board.set_fen("4k3/8/8/8/8/8/1N6/4K3 w - - 0 1")
    index = chess.algebraic_to_board_index("b2")
    with check:
        assert board.get_legal_moves(index) == unordered(["b2-a4", "b2-c4", "b2-d1", "b2-d3"])

    board.set_fen("1N2k3/8/8/8/8/8/8/4K3 b - - 0 1")
    index = chess.algebraic_to_board_index("b8")
    with check:
        assert board.get_legal_moves(index) == unordered(["b8-a6", "b8-c6", "b8-d7"])

    board.set_fen("6k1/8/8/8/8/8/8/4K1N1 w - - 0 1")
    index = chess.algebraic_to_board_index("g1")
    with check:
        assert board.get_legal_moves(index) == unordered(["g1-f3", "g1-h3", "g1-e2"])

    board.set_fen("6k1/8/8/8/8/6N1/8/4K3 w - - 0 1")
    index = chess.algebraic_to_board_index("g3")
    with check:
        assert board.get_legal_moves(index) == unordered(["g3-f5", "g3-h5", "g3-e4", "g3-e2", "g3-f1", "g3-h1"])

    board.set_fen("6k1/8/8/8/8/8/7N/4K3 w - - 0 1")
    index = chess.algebraic_to_board_index("h2")
    with check:
        assert board.get_legal_moves(index) == unordered(["h2-g4", "h2-f3", "h2-f1"])


def test_legal_rook_moves():
    board.set_fen("4k3/8/1r6/8/7p/8/8/4K2R w - - 0 1")
    index = chess.algebraic_to_board_index("h1")
    with check:
        assert board.get_legal_moves(index) == unordered(["h1-g1", "h1-f1", "h1-h2", "h1-h3", "h1xh4"])
    index = chess.algebraic_to_board_index("b6")
    with check:
        assert board.get_legal_moves(index) == unordered(
            [
                "b6-b7",
                "b6-b8",
                "b6-b5",
                "b6-b4",
                "b6-b3",
                "b6-b2",
                "b6-b1",
                "b6-a6",
                "b6-c6",
                "b6-d6",
                "b6-e6",
                "b6-f6",
                "b6-g6",
                "b6-h6",
            ]
        )


def test_legal_bishop_moves():
    board.set_fen("4k3/3b4/8/8/4B1P1/8/8/4K3 w - - 0 1")
    index = chess.algebraic_to_board_index("e4")
    with check:
        assert board.get_legal_moves(index) == unordered(
            [
                "e4-d5",
                "e4-c6",
                "e4-b7",
                "e4-a8",
                "e4-d3",
                "e4-c2",
                "e4-b1",
                "e4-f5",
                "e4-g6",
                "e4-h7",
                "e4-f3",
                "e4-g2",
                "e4-h1",
            ]
        )
    index = chess.algebraic_to_board_index("d7")
    with check:
        assert board.get_legal_moves(index) == unordered(
            ["d7-c8", "d7-c6", "d7-b5", "d7-a4", "d7-e6", "d7-f5", "d7xg4"]
        )


def test_enpassant_moves():
    board.set_fen("6k1/8/8/8/5Pp1/8/8/4K1R1 b - f3 0 1")
    index = chess.algebraic_to_board_index("g4")
    with check:
        assert board.get_legal_moves(index) == unordered(["g4-g3"])

    board.set_fen("5k2/8/8/8/5Pp1/8/8/4K1R1 b - f3 0 1")
    index = chess.algebraic_to_board_index("g4")
    with check:
        assert board.get_legal_moves(index) == unordered(["g4xf3e.p.", "g4-g3"])

    board.set_fen("8/8/8/8/k4PpR/8/8/4K3 b - f3 0 1")
    index = chess.algebraic_to_board_index("g4")
    with check:
        assert board.get_legal_moves(index) == unordered(["g4-g3"])

    board.set_fen("8/8/8/2k5/2pP4/8/B7/4K3 b - d3 0 3")
    index = chess.algebraic_to_board_index("c4")
    with check:
        assert board.get_legal_moves(index) == unordered(["c4xd3e.p."])

    board.set_fen("8/8/8/2k5/2pP4/8/B7/4K3 b - d3 0 3")
    with check:
        board.make_move("c4xd3e.p.")
        assert board.get_fen() == "8/8/8/2k5/8/3p4/B7/4K3 w - - 0 4"

    board.set_fen("8/8/2k5/8/2pP4/8/B7/4K3 b - d3 0 3")
    with check:
        board.make_move("c6-d5")
        assert board.get_fen() == "8/8/8/3k4/2pP4/8/B7/4K3 w - - 1 4"


def test_checked_king_escape_moves():
    board.set_fen("r3k2r/p1pp1pb1/bn2Qnp1/2qPN3/1p2P3/2N5/PPPBBPPP/R3K2R b KQkq - 3 2")
    with check:
        assert board.is_check("b") is True
        assert board.is_checkmate("b") is False
    index = chess.algebraic_to_board_index("e8")
    with check:
        assert board.get_legal_moves(index) == unordered(["e8-d8", "e8-f8"])
    with check:
        assert board.all_legal_moves("b") == unordered(["e8-d8", "e8-f8", "c5-e7", "d7xe6", "f7xe6"])


def test_castling_moves():
    board.set_fen("r3k2r/p1pp1pb1/bn2Qnp1/2qPN3/1p2P3/2N5/PPPBBPPP/R3K2R b KQkq - 3 2")
    with check:
        index = board.board.index("k")
        assert board.check_castle(index, "b") is False
    with check:
        index = board.board.index("K")
        assert board.check_castle(index, "w") is True

    board.set_fen("r3k2r/p1ppqpb1/bn2Qnp1/3PN3/1p2P3/2N5/PPPBBPPP/R3K2R b KQkq - 3 2")
    with check:
        board.make_move("O-O", "b")
        assert board.get_fen() == "r4rk1/p1ppqpb1/bn2Qnp1/3PN3/1p2P3/2N5/PPPBBPPP/R3K2R w KQ - 4 3"

    board.set_fen("r3k2r/p1ppqpb1/bn2Qnp1/3PN3/1p2P3/2N5/PPPBBPPP/R3K2R b KQkq - 3 2")
    with check:
        board.make_move("O-O-O", "b")
        assert board.get_fen() == "2kr3r/p1ppqpb1/bn2Qnp1/3PN3/1p2P3/2N5/PPPBBPPP/R3K2R w KQ - 4 3"

    board.set_fen("r3k2r/p1ppqpb1/bn2Qnp1/3PN3/1p2P3/2N5/PPPBBPPP/R3K2R w KQkq - 3 2")
    with check:
        board.make_move("O-O-O", "w")
        assert board.get_fen() == "r3k2r/p1ppqpb1/bn2Qnp1/3PN3/1p2P3/2N5/PPPBBPPP/2KR3R b kq - 4 2"

    board.set_fen("r3k2r/p1ppqpb1/bn2Qnp1/3PN3/1p2P3/2N5/PPPBBPPP/R3K2R w KQkq - 3 2")
    with check:
        board.make_move("O-O", "w")
        assert board.get_fen() == "r3k2r/p1ppqpb1/bn2Qnp1/3PN3/1p2P3/2N5/PPPBBPPP/R4RK1 b kq - 4 2"


def test_promotion():
    board.set_fen("4k3/8/8/8/8/8/1p6/2B1K3 b - - 0 1")
    with check:
        index = chess.algebraic_to_board_index("b2")
        assert board.get_legal_moves(index) == unordered(
            ["b2-b1=q", "b2-b1=r", "b2-b1=b", "b2-b1=n", "b2xc1=q", "b2xc1=r", "b2xc1=b", "b2xc1=n"]
        )

    board.set_fen("1b2k3/2P5/8/8/8/8/8/4K3 w - - 0 1")
    with check:
        index = chess.algebraic_to_board_index("c7")
        assert board.get_legal_moves(index) == unordered(
            ["c7-c8=Q", "c7-c8=R", "c7-c8=B", "c7-c8=N", "c7xb8=Q", "c7xb8=R", "c7xb8=B", "c7xb8=N"]
        )
    with check:
        board.make_move("c7-c8=Q")
        assert board.get_fen() == "1bQ1k3/8/8/8/8/8/8/4K3 b - - 0 1"
        assert board.is_check("b") is True


def test_checkmate():
    board.set_fen("1bQ1k3/7R/8/8/8/8/8/4K3 b - - 0 1")
    with check:
        assert board.is_checkmate("b") is True
        assert board.is_checkmate("w") is False
        assert board.is_stalemate("b") is False
        assert board.is_stalemate("w") is False


def test_stalemate():
    board.set_fen("6k1/7R/8/8/8/8/5Q2/4K2R b - - 0 1")
    with check:
        assert board.is_checkmate("b") is False
        assert board.is_checkmate("w") is False
        assert board.is_stalemate("b") is True
        assert board.is_stalemate("w") is False


def test_all_legal_moves_for_various_positions():
    board.set_fen("2kr3r/p1ppqpb1/bn2Qnp1/3PN3/1p2P3/2N5/PPPBBPPP/R3K2R b KQ - 3 2")
    with check:
        moves = board.all_legal_moves("b")
        assert len(moves) == 44

    board.set_fen("rnb2k1r/pp1Pbppp/2p5/q7/2B5/8/PPPQNnPP/RNB1K2R w KQ - 3 9")
    with check:
        moves = board.all_legal_moves("w")
        assert len(moves) == 39

    board.set_fen("2r5/3pk3/8/2P5/8/2K5/8/8 w - - 5 4")
    with check:
        moves = board.all_legal_moves("w")
        assert len(moves) == 9
