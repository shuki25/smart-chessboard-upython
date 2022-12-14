"""
Chessboard LED Class:

This class is used to control the chessboard LED. It is a 8x8 LED matrix
that is controlled by LED chip WS2812B. The LED driver chip is
controlled by ESP32.

The LED chip is controlled by 3 wires: VCC, GND and DIN. The DIN is
connected to GPIO 18 of ESP32. The VCC and GND are connected to 5V and
GND of ESP32.  The ESP32 pin voltage output is 3.3V, so the level shifter
is needed to convert the 3.3V to 5V with the help of a level shifter chip.

The LED chip is controlled by a serial protocol called WS2812B protocol.
The protocol is described in the following link:
https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf

The class provides the following methods:
    - __init__: initialize the LED driver chip
    - clear_board: clear the LED matrix
    - show_occupied_squares: show the occupied squares on the LED matrix
    - show_unoccupied_squares: show the unoccupied squares on the LED matrix
    - show_legal_moves: show the legal moves on the LED matrix
"""

from neopixel import NeoPixel
import chess
import machine
from chessboard import Chessboard
import uasyncio


class ChessboardLED:

    neopixel_gpio = None
    driver: NeoPixel = None

    def __init__(self, driver: NeoPixel = None, led_io: machine.Pin = None, vls_io: machine.Pin = None):
        """
        Create a ChessboardLed object

        :param driver: NeoPixel driver
        :param led_io: IO pin to use for the LED

        :return: None
        """
        if led_io is None:
            raise Exception("led_io parameter is required")

        if driver is None:
            self.driver = NeoPixel(led_io, 64)

        if vls_io is None:
            raise Exception("vls_io parameter is required")

        self.vls_enable = vls_io
        self.vls_enable.value(1)

    def clear_board(self):
        """
        Clear the LED matrix

        :return: None
        """
        self.driver.fill((0, 0, 0))
        self.driver.write()

    def show_occupied_squares(self, board: Chessboard):
        """
        Show the occupied squares on the LED matrix

        :param board: Chessboard object

        :return: None
        """
        self.driver.fill((0, 0, 0))
        for i, occupied in enumerate(board.bitboard):
            if occupied:
                self.driver[i] = (0, 0, 32)
        self.driver.write()

    def show_unoccupied_squares(self, board: Chessboard):
        """
        Show the unoccupied squares on the LED matrix

        :param board: Chessboard object

        :return: None
        """
        self.driver.fill((0, 0, 0))
        for i, occupied in enumerate(board.bitboard):
            if not occupied:
                self.driver[i] = (32, 0, 0)
        self.driver.write()

    def show_setup_squares(self, board: Chessboard):
        """
        Show the setup squares on the LED matrix

        :param board: Chessboard object

        :return: None
        """
        self.driver.fill((0, 0, 0))
        mask = []
        for i, occupied in enumerate(board.bitboard):
            if not occupied and i // 8 in [0, 1, 6, 7]:
                mask.append(i)
                self.driver[i] = (128, 0, 8)
        self.driver.write()

    def show_interim_move(self, move: str, side: str):
        """
        Show the interim move on the LED matrix

        :param move: move in algebraic notation
        :param side: side to move

        :return: None
        """

        from_square, to_square, capture, promotion, enpassant, castle = chess.parse_move_notation(move)

        self.driver.fill((0, 0, 0))

        if not castle:
            from_index = chess.algebraic_to_board_index(from_square)
            to_index = chess.algebraic_to_board_index(to_square)
            self.driver[from_index] = (0, 0, 18)
            if capture:
                self.driver[to_index] = (255, 0, 0)
            elif promotion:
                self.driver[to_index] = (0, 100, 100)
            else:
                self.driver[to_index] = (155, 65, 0)
        else:
            if castle == "K" and side == "w":
                self.driver[4] = (0, 0, 18)
                self.driver[5] = (155, 65, 0)
                self.driver[6] = (155, 65, 0)
                self.driver[7] = (0, 0, 18)
            elif castle == "Q" and side == "w":
                self.driver[4] = (0, 0, 18)
                self.driver[3] = (155, 65, 0)
                self.driver[2] = (155, 65, 0)
                self.driver[0] = (0, 0, 18)
            elif castle == "K" and side == "b":
                self.driver[60] = (0, 0, 18)
                self.driver[61] = (155, 65, 0)
                self.driver[62] = (155, 65, 0)
                self.driver[63] = (0, 0, 18)
            elif castle == "Q" and side == "b":
                self.driver[60] = (0, 0, 18)
                self.driver[59] = (155, 65, 0)
                self.driver[58] = (155, 65, 0)
                self.driver[56] = (0, 0, 18)

        self.driver.write()

    def show_legal_moves(self, origin, board: chess.Chess):
        """
        Show the legal moves on the LED matrix

        :param origin: origin square
        :param board: Chess object

        :return: None
        """
        if origin is None:
            return

        origin_square = chess.algebraic_to_board_index(origin)
        if board[origin_square] is None:
            return

        side = 'w' if board[origin_square].isupper() else 'b'
        if side != board.turn:
            self.driver.fill((64, 0, 0))
            self.driver[origin_square] = (0, 0, 64)
            self.driver.write()
            return

        self.driver.fill((0, 0, 0))
        self.driver[origin_square] = (0, 0, 64)

        legal_moves = board.get_legal_moves(origin_square)
        print(legal_moves)

        for i, move in enumerate(legal_moves):
            from_square, to_square, capture, promotion, enpassant, castle = chess.parse_move_notation(move)
            if castle:
                if castle in "Kk":
                    if side == 'b':
                        self.driver[61] = (0, 100, 64)
                        self.driver[62] = (0, 100, 0)
                        self.driver[63] = (100, 100, 100)
                    else:
                        self.driver[5] = (0, 100, 64)
                        self.driver[6] = (0, 100, 0)
                        self.driver[7] = (100, 100, 100)
                elif castle in "Qq":
                    if side == 'b':
                        self.driver[59] = (0, 100, 64)
                        self.driver[58] = (0, 100, 0)
                        self.driver[56] = (100, 100, 100)
                    else:
                        self.driver[3] = (0, 100, 64)
                        self.driver[2] = (0, 100, 0)
                        self.driver[0] = (100, 100, 100)
            else:
                index = chess.algebraic_to_board_index(to_square)
                if capture:
                    self.driver[index] = (100, 0, 0)
                elif promotion:
                    self.driver[index] = (0, 100, 100)
                else:
                    self.driver[index] = (0, 32, 0)
        self.driver.write()

    async def wagtag(self, period_ms=100):
        """
        Police Wagtag lights of the LED matrix

        :param period_ms: period of the wagtag in milliseconds

        :return: None
        """

        self.driver.fill((0, 0, 0))
        self.driver.write()

        ticks = 0

        while True:
            if ticks % 2 == 0:
                self.driver.fill((0, 0, 0))
                self.driver.write()
                await uasyncio.sleep_ms(50)
                for i in range(0, int(pixel / 2)):
                    self.driver[i] = (0, 0, 64)
            else:
                self.driver.fill((0, 0, 0))
                self.driver.write()
                await uasyncio.sleep_ms(50)
                for i in range(int(pixel / 2), int(pixel)):
                    self.driver[i] = (64, 0, 0)
            self.driver.write()
            ticks += 1
            await uasyncio.sleep_ms(period_ms)