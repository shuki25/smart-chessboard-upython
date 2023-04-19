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
    - rgb_test: test the LED matrix by showing different colors
"""

from neopixel import NeoPixel
import chess
import machine
from chessboard import Chessboard
import uasyncio

LUX_MAX = 32768


def calculate_proportion(a: int, b: int, c: int, base: int = 10, max_val: int = 255):
    """
    Calculate the proportion of the given values

    :param a: Value 1
    :param b: Value 2
    :param c: Value 3
    :param base: Base value
    :param max_val: Maximum value

    :return: Proportion of the given values
    """
    if a == 0:
        return 0

    n = base + int((a * b) / c)

    if n > max_val:
        n = max_val

    return n


class ChessboardLED:

    neopixel_gpio = None
    driver: NeoPixel = None
    test_mode = False
    max_brightness = 175
    min_brightness = 10
    led_count = 64
    lux = 0

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
            self.driver = NeoPixel(led_io, self.led_count)

        if vls_io is None:
            raise Exception("vls_io parameter is required")

        self.vls_enable = vls_io
        # set pin to low to enable buffer gate
        self.vls_enable.value(0)

    def set_lux(self, lux):
        """
        Set the lux value

        :param lux: Lux value

        :return: None
        """
        self.lux = lux

    def adjust_brightness(self, color: tuple, lux=None):
        """
        Adjust the brightness of the LED

        :param color: RGB color
        :param lux: Lux value

        :return: Adjusted RGB color
        """
        if lux is None:
            lux = self.lux

        if lux > (LUX_MAX * 0.03125):
            lux = LUX_MAX * 0.03125

        adj_max_brightness = self.max_brightness * ((lux // (LUX_MAX * 0.003125)) + 1) / 10

        adj_color = (
            calculate_proportion(
                color[0], adj_max_brightness, self.max_brightness, self.min_brightness, self.max_brightness
            ),
            calculate_proportion(
                color[1], adj_max_brightness, self.max_brightness, self.min_brightness, self.max_brightness
            ),
            calculate_proportion(
                color[2], adj_max_brightness, self.max_brightness, self.min_brightness, self.max_brightness
            ),
        )
        # print("lux: {}, adj_max_brightness: {}".format(lux, adj_max_brightness))
        # print("adj_color: {}".format(adj_color))

        return adj_color

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
                self.driver[i] = self.adjust_brightness((0, 0, 32))
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
                self.driver[i] = self.adjust_brightness((32, 0, 0))
        self.driver.write()

    def show_checkmate(self, side: str):
        """
        Show the checkmate on the LED matrix

        :param side: Side of the checkmate

        :return: None
        """
        self.driver.fill((0, 0, 0))
        for i in range(64):
            if i < 32:
                if side == "w":
                    self.driver[i] = self.adjust_brightness((100, 0, 0))
                else:
                    self.driver[i] = self.adjust_brightness((0, 48, 0))
            else:
                if side == "b":
                    self.driver[i] = self.adjust_brightness((100, 0, 0))
                else:
                    self.driver[i] = self.adjust_brightness((0, 48, 0))

        self.driver.write()

    def show_stalemate(self):
        """
        Show the stalemate on the LED matrix

        :return: None
        """
        self.driver.fill((0, 0, 0))
        for i in range(64):
            if i % 8 < 4:
                if i // 8 < 4:
                    self.driver[i] = self.adjust_brightness((0, 0, 48))
                else:
                    self.driver[i] = self.adjust_brightness((0, 48, 0))
            else:
                if i // 8 < 4:
                    self.driver[i] = self.adjust_brightness((0, 48, 0))
                else:
                    self.driver[i] = self.adjust_brightness((0, 0, 48))

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
                self.driver[i] = self.adjust_brightness((128, 0, 8))
        self.driver.write()

    def show_bitboard_squares(self, bitboard: int, color: tuple = (0, 0, 32)):
        """
        Show the bitboard squares on the LED matrix

        :param bitboard: bitboard
        :param color: color of the LED

        :return: None
        """
        self.driver.fill((0, 0, 0))
        for i in range(64):
            if bitboard & (1 << i):
                self.driver[i] = self.adjust_brightness(color)
        self.driver.write()

    def zero_bitboard_squares(self):
        """
        Zero the bitboard squares on the LED matrix

        :param bitboard: bitboard

        :return: None
        """
        self.driver.fill((0, 0, 0))

    def prepare_bitboard_square(self, bitboard: int, color: tuple = (0, 0, 32)):
        """
        Prepare the bitboard squares on the LED matrix

        :param bitboard: bitboard
        :param color: color of the LED

        :return: None
        """
        for i in range(64):
            if bitboard & (1 << i):
                self.driver[i] = self.adjust_brightness(color)

    def display_bitboard_squares(self):
        """
        Display the bitboard squares on the LED matrix

        :return: None
        """
        self.driver.write()


    def show_cpu_remote_move(self, move: str, side: str):
        """
        Show the CPU remote move on the LED matrix

        :param move: move in algebraic notation
        :param side: side to move
        """

        from_square, to_square, capture, promotion, enpassant, castle = chess.parse_move_notation(move)

        if not castle:
            from_index = chess.algebraic_to_board_index(from_square)
            to_index = chess.algebraic_to_board_index(to_square)
            self.driver[from_index] = self.adjust_brightness((0, 0, 32))
            if capture:
                self.driver[to_index] = self.adjust_brightness((255, 0, 0))
            elif promotion:
                self.driver[to_index] = self.adjust_brightness((0, 100, 100))
            else:
                self.driver[to_index] = self.adjust_brightness((0, 155, 0))
        else:
            if castle == "K" and side == "w":
                self.driver[4] = self.adjust_brightness((0, 0, 18))
                self.driver[5] = self.adjust_brightness((155, 65, 0))
                self.driver[6] = self.adjust_brightness((155, 65, 0))
                self.driver[7] = self.adjust_brightness((0, 0, 18))
            elif castle == "Q" and side == "w":
                self.driver[4] = self.adjust_brightness((0, 0, 18))
                self.driver[3] = self.adjust_brightness((155, 65, 0))
                self.driver[2] = self.adjust_brightness((155, 65, 0))
                self.driver[0] = self.adjust_brightness((0, 0, 18))
            elif castle == "K" and side == "b":
                self.driver[60] = self.adjust_brightness((0, 0, 18))
                self.driver[61] = self.adjust_brightness((155, 65, 0))
                self.driver[62] = self.adjust_brightness((155, 65, 0))
                self.driver[63] = self.adjust_brightness((0, 0, 18))
            elif castle == "Q" and side == "b":
                self.driver[60] = self.adjust_brightness((0, 0, 18))
                self.driver[59] = self.adjust_brightness((155, 65, 0))
                self.driver[58] = self.adjust_brightness((155, 65, 0))
                self.driver[56] = self.adjust_brightness((0, 0, 18))

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
            self.driver[from_index] = self.adjust_brightness((0, 0, 18))
            if capture:
                self.driver[to_index] = self.adjust_brightness((255, 0, 0))
            elif promotion:
                self.driver[to_index] = self.adjust_brightness((0, 100, 100))
            else:
                self.driver[to_index] = self.adjust_brightness((155, 65, 0))
        else:
            if castle == "K" and side == "w":
                self.driver[4] = self.adjust_brightness((0, 0, 18))
                self.driver[5] = self.adjust_brightness((155, 65, 0))
                self.driver[6] = self.adjust_brightness((155, 65, 0))
                self.driver[7] = self.adjust_brightness((0, 0, 18))
            elif castle == "Q" and side == "w":
                self.driver[4] = self.adjust_brightness((0, 0, 18))
                self.driver[3] = self.adjust_brightness((155, 65, 0))
                self.driver[2] = self.adjust_brightness((155, 65, 0))
                self.driver[0] = self.adjust_brightness((0, 0, 18))
            elif castle == "K" and side == "b":
                self.driver[60] = self.adjust_brightness((0, 0, 18))
                self.driver[61] = self.adjust_brightness((155, 65, 0))
                self.driver[62] = self.adjust_brightness((155, 65, 0))
                self.driver[63] = self.adjust_brightness((0, 0, 18))
            elif castle == "Q" and side == "b":
                self.driver[60] = self.adjust_brightness((0, 0, 18))
                self.driver[59] = self.adjust_brightness((155, 65, 0))
                self.driver[58] = self.adjust_brightness((155, 65, 0))
                self.driver[56] = self.adjust_brightness((0, 0, 18))

        self.driver.write()

    def show_illegal_piece_lifted(self, origin: str, board: chess.Chess):
        if origin is None:
            return

        origin_square = chess.algebraic_to_board_index(origin)
        if board[origin_square] is None:
            return

        self.driver.fill((64, 0, 0))
        self.driver[origin_square] = self.adjust_brightness((0, 0, 64))
        self.driver.write()
        return

    def show_legal_moves(self, origin:str, legal_moves: list, board: chess.Chess):
        """
        Show the legal moves on the LED matrix

        :param origin: origin square
        :param legal_moves: list of legal moves
        :param board: chess board

        :return: None
        """
        if origin is None:
            return

        origin_square = chess.algebraic_to_board_index(origin)
        if board[origin_square] is None:
            return

        side = "w" if board[origin_square].isupper() else "b"
        if side != board.turn:
            self.driver.fill((64, 0, 0))
            self.driver[origin_square] = self.adjust_brightness((0, 0, 64))
            self.driver.write()
            return

        self.driver.fill((0, 0, 0))
        self.driver[origin_square] = self.adjust_brightness((0, 0, 64))

        for i, move in enumerate(legal_moves):
            from_square, to_square, capture, promotion, enpassant, castle = chess.parse_move_notation(move)
            if castle:
                if castle in "Kk":
                    if side == "b":
                        self.driver[62] = self.adjust_brightness((0, 32, 0))
                    else:
                        self.driver[6] = self.adjust_brightness((0, 32, 0))
                elif castle in "Qq":
                    if side == "b":
                        self.driver[58] = self.adjust_brightness((0, 32, 0))
                    else:
                        self.driver[2] = self.adjust_brightness((0, 32, 0))
            else:
                index = chess.algebraic_to_board_index(to_square)
                if capture:
                    self.driver[index] = self.adjust_brightness((100, 0, 0))
                elif promotion:
                    self.driver[index] = self.adjust_brightness((0, 100, 100))
                else:
                    self.driver[index] = self.adjust_brightness((0, 32, 0))
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
        pixel = 64

        while True:
            if ticks % 2 == 0:
                self.driver.fill((0, 0, 0))
                self.driver.write()
                await uasyncio.sleep_ms(50)
                for i in range(0, int(pixel / 2)):
                    self.driver[i] = self.adjust_brightness((0, 0, 64))
            else:
                self.driver.fill((0, 0, 0))
                self.driver.write()
                await uasyncio.sleep_ms(50)
                for i in range(int(pixel / 2), int(pixel)):
                    self.driver[i] = self.adjust_brightness((64, 0, 0))
            self.driver.write()
            ticks += 1
            await uasyncio.sleep_ms(period_ms)

    def wheel(self, pos):
        """
        Generate rainbow colors across 0-255 positions.

        :param pos: position

        :return: color
        """
        if pos < self.max_brightness // 3:
            return self.max_brightness - pos * 3, pos * 3, 0
        elif pos < self.max_brightness * 2 // 3:
            pos -= self.max_brightness // 3
            return 0, self.max_brightness - pos * 3, pos * 3
        else:
            pos -= self.max_brightness * 2 // 3
            return pos * 3, 0, self.max_brightness - pos * 3

    async def rgb_test(self, console):
        """
        Test the RGB LED matrix

        :return: None
        """
        n = self.led_count

        await console("", clear=True)
        # cycle
        await console("Running Cycle...")
        for i in range(4 * n):
            for j in range(n):
                self.driver[j] = (0, 0, 0)
            self.driver[i % n] = (self.max_brightness, self.max_brightness, self.max_brightness)
            self.driver.write()
            await uasyncio.sleep_ms(25)

        # bounce
        await console("Done\\rRunning Bounce...")
        k = 0
        square_color = (0, 0, 0)
        for i in range(4 * n):
            if i % 4 == 0:
                k += 1
                if k % 2 == 0:
                    square_color = (self.max_brightness // 2, 0, 0)
                elif k % 3 == 0:
                    square_color = (0, self.max_brightness // 2, 0)
                else:
                    square_color = (0, 0, self.max_brightness // 2)
            for j in range(n):
                self.driver[j] = square_color
            if (i // n) % 2 == 0:
                self.driver[i % n] = (0, 0, 0)
            else:
                self.driver[n - 1 - (i % n)] = (0, 0, 0)
            self.driver.write()
            await uasyncio.sleep_ms(60)

        await console("Done\\rRunning Fade in/out...")
        # fade in/out
        for i in range(0, 4 * 256, 8):
            for j in range(n):
                if (i // 256) % 2 == 0:
                    val = i & 0xFF
                else:
                    val = 255 - (i & 0xFF)
                self.driver[j] = (val, 0, 0)
            self.driver.write()

        # rainbow
        await console("Done\\rRunning Rainbow...")
        for j in range(self.max_brightness):
            for i in range(n):
                pixel_index = (i * self.max_brightness // n) + j
                self.driver[i] = self.wheel(pixel_index & self.max_brightness)
            self.driver.write()
            await uasyncio.sleep_ms(20)

        await console("Done\\rClearing LED matrix...")
        # clear the LED matrix
        self.driver.fill((0, 0, 0))
        self.driver.write()

        await console("Done\\rAddressable LED matrix test complete")
