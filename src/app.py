import sys

import esp32
import machine
import ntptime
import uasyncio
import ubinascii
import os

import nextion
import wifimgr
from primitives.queue import Queue
from i2c_multiplex import I2CMultiplex
from chess import Chess
from chessboard import Chessboard, INVERSE_MASK, STARTING_POSITION
from chess_clock import ChessClock
from chessboard_led import ChessboardLED

# Constants
IO_EXPANDER_0_ADDRESS = 0x20
IO_EXPANDER_1_ADDRESS = 0x21
IO_EXPANDER_2_ADDRESS = 0x22
IO_EXPANDER_3_ADDRESS = 0x23

# UI Buttons
BUTTON_WHITE = 13
BUTTON_BLACK = 12

# Initialization
i2c_mux_addr = 0x70
i2c: machine.I2C
i2c_mux: I2CMultiplex
chessboard_gpio_addr = [IO_EXPANDER_0_ADDRESS, IO_EXPANDER_1_ADDRESS, IO_EXPANDER_2_ADDRESS, IO_EXPANDER_3_ADDRESS]
chessboard: Chessboard
board: dict
board_status: int
sd_card_mounted = False
white_clock: ChessClock
black_clock: ChessClock
chessboard_led: ChessboardLED
game: Chess

# Pin definitions
repl_button = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
i2c_mux_enable = machine.Pin(4, machine.Pin.OUT, machine.Pin.PULL_UP)
led_strip = machine.Pin(25, machine.Pin.OUT)
vls_enable = machine.Pin(26, machine.Pin.OUT, machine.Pin.PULL_UP)
sd_card_detect = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)
i2c_sda = machine.Pin(21)
i2c_scl = machine.Pin(22)

# I/O Expander Interrupts
io_interrupt = machine.Pin(34, machine.Pin.IN, machine.Pin.PULL_UP)
io_interrupt1 = machine.Pin(35, machine.Pin.IN, machine.Pin.PULL_UP)
io_interrupt2 = machine.Pin(33, machine.Pin.IN, machine.Pin.PULL_UP)
io_interrupt3 = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)
io_interrupts = [io_interrupt, io_interrupt1, io_interrupt2, io_interrupt3]

# UI Tacile Buttons
button_black = machine.Pin(12, machine.Pin.IN, machine.Pin.PULL_UP)
button_white = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)

# UART Serial communication
print("setting up serial")
uart = machine.UART(1, 115200, tx=17, rx=16)
uart.deinit()

# Uasyncio lock object
lock = uasyncio.Lock()

# Initialize Queue for synchronizing UART messages
queue = Queue()

# Nextion display
tft: nextion.Nextion

# Initialize variables
wifi_connected = 0
# wlan = network.WLAN(network.STA_IF)
wlan = None
rtc = machine.RTC()
is_24h = False
device_id = ubinascii.hexlify(machine.unique_id())
hopper_ticks = 0
previous_tick = 0
io_expander_interrupt_flag = False
button_interrupt_flag = False
button_interrupt_id = None


async def blink(led, period_ms):
    while True:
        led.value(not led.value())
        await uasyncio.sleep_ms(period_ms)


async def wifi_blink(led, period_ms):
    global wlan
    global wifi_connected

    counter = 0
    while not wifi_connected:
        if wlan is not None:
            if wlan.status() == 205 and counter > 4:
                led.value(0)
                await uasyncio.sleep_ms(period_ms * 4)
                counter = 0
        else:
            led.value(not led.value())
        counter += 1
        await uasyncio.sleep_ms(period_ms)
    led.value(1)


async def connect_wifi():
    global wlan
    global wifi_connected

    connect_status = False

    print("connecting to wifi")
    have_sd = False
    if not sd_card_detect.value() and sd_card_mounted:
        have_sd = True
    wlan = wifimgr.get_connection(have_sd)

    while True:
        if wlan is None:
            pass
        else:
            wifi_connected = True
            await uasyncio.sleep_ms(200)
            ntptime.settime()
            break
        await uasyncio.sleep_ms(200)
    print("connected to wifi")
    print(wlan.ifconfig())


async def event_listener():
    global tft, queue, lock, rtc, game
    global io_expander_interrupt_flag, chessboard, board, board_status, i2c
    global white_clock, black_clock, i2c_mux, button_interrupt_flag, button_interrupt_id

    msg_count = 0
    loop_counter = 0
    is_display_sleeping = False
    prev_board_status = board_status
    prev_ui_state = 0
    ui_state = 0
    curr_pieces = 0
    board_state_piece_lifted = 0
    board_state_capturing_piece = 0
    board_state_captured_piece = 0
    game_in_progress = False
    legal_moves = []

    chessboard.read_board()
    board_status, board = chessboard.get_board()
    curr_pieces = chessboard.count_pieces(board_status)
    simulated_board_status = board_status
    print("Initial board status: {}".format(board_status))
    capture_flag = False
    piece_removed = False
    position_changed_flag = False
    show_setup_message = False
    piece_coordinate = None
    move_notation = None
    previous_position = None

    white_clock = ChessClock(i2c, i2c_mux, [0, 3])
    black_clock = ChessClock(i2c, i2c_mux, [0, 2])

    while True:
        if not lock.locked():
            await lock.acquire()
            await tft.flush_buffer()
            lock.release()

        qs = queue.qsize()
        event = None
        data = None

        if qs:
            msg_count += 1
            message = queue.get_nowait()
            print("%s message [%s]: %s" % (rtc.datetime(), msg_count, message))
            event, data = await tft.parse_event(message)

        if event == nextion.TOUCH:
            (page, component, touch) = data
            print("Touch event: Page %s, Component %s, Touch %s" % data)

            # CPU temperature button pressed
            if page == 1 and component == 20:
                tf = esp32.raw_temperature()
                tc = (tf - 32.0) / 1.8
                temp = "{0:3.1f}".format(tc)
                await tft.set_value("page7.cpu_temp.txt", str(temp))

            # Manual feed button pressed
            if page == 1 and component == 12:
                await dispense_food(4)
                await tft.send_command("page page1")
                await uasyncio.sleep(3)

        if event == nextion.TOUCH_IN_SLEEP:
            (page, component, touch) = data
            print("Touch in sleep event: Page %s, Component %s, Touch %s" % data)

        if not game_in_progress and not show_setup_message:
            print("Set up the playing pieces on the board")
            show_setup_message = True
            white_clock.display_text("Set up board to", 0, 0)
            white_clock.display_text("starting position.", 0, 10, clear=False)
            prev_board_status, board = chessboard.get_board()
            chessboard_led.show_setup_squares(chessboard)
            while True:
                chessboard.read_board()
                board_status, board = chessboard.get_board()
                if board_status != prev_board_status:
                    chessboard_led.show_setup_squares(chessboard)
                if board_status == STARTING_POSITION:
                    break
                await uasyncio.sleep_ms(500)
            white_clock.display_text("Ready to start.", 0, 0)
            white_clock.display_text("Press the button", 0, 10, clear=False)
            white_clock.display_text("to start game.", 0, 20, clear=False)
            prev_board_status = board_status
            simulated_board_status = board_status

        if button_interrupt_flag:
            button_interrupt_flag = False

            if not button_white.value() and not button_black.value() and game_in_progress:
                print("Both buttons pressed")
                print("Resetting board positions")
                game_in_progress = False
                show_setup_message = False
                white_clock.display_text("Game reset.", 0, 0)
                black_clock.display_text("Game reset.", 0, 0)
                piece_removed = False
                capture_flag = False
                board_state_piece_lifted = 0
                board_state_capturing_piece = 0
                board_state_captured_piece = 0
                position_changed_flag = False
                chessboard.reset_board()
                chessboard.read_board()
                board_status, board = chessboard.get_board()
                prev_board_status = board_status
                simulated_board_status = board_status
                curr_pieces = chessboard.count_pieces(board_status)
                chessboard.print_board()
            elif not button_white.value() and not game_in_progress:
                game_in_progress = True
                game = Chess()
                print("turn: {}".format(game.turn))
                white_clock.set_clock(900)
                white_clock.start_clock()
                black_clock.set_clock(900)
            elif game_in_progress:
                if not button_white.value() and game.turn == 'w':
                    print("White button pressed")
                    if game.check_move(move_notation, side='w'):
                        print("Valid move")
                        chessboard_led.clear_board()
                        game.make_move(move_notation, side='w')
                        white_clock.stop_clock()
                        black_clock.start_clock()
                    else:
                        print("Invalid move")
                        chessboard_led.clear_board()
                        await uasyncio.sleep_ms(1000)
                        chessboard_led.clear_board()
                elif not button_black.value() and game.turn == 'b':
                    print("Black button pressed")
                    if game.check_move(move_notation, side='b'):
                        print("Valid move")
                        chessboard_led.clear_board()
                        game.make_move(move_notation, side='b')
                        black_clock.stop_clock()
                        white_clock.start_clock()
                    else:
                        print("Invalid move")
                        chessboard_led.clear_board()
                        await uasyncio.sleep_ms(1000)
                        chessboard_led.clear_board()
                print("turn: {}".format(game.turn))
                print(game)

        # Simulate io_expander interrupt (due to errorenous pin assignment in schematic)
        chessboard.read_board()
        board_status, board = chessboard.get_board()
        if board_status != simulated_board_status:
            io_expander_interrupt_flag = True
            simulated_board_status = board_status
            print("Simulated IO Expander interrupt")

        if io_expander_interrupt_flag and game_in_progress:
            io_expander_interrupt_flag = False
            print("IO Expander interrupt")
            chessboard.read_board()
            board_status, board = chessboard.get_board()
            if not position_changed_flag and board_status != prev_board_status:
                position_changed_flag = True
                print("board position changed")
            if position_changed_flag:
                num_pieces = chessboard.count_pieces(board_status)
                if num_pieces < curr_pieces:
                    if curr_pieces - num_pieces == 1 and not capture_flag:
                        piece_removed = True
                        piece_coordinate = chessboard.coord_to_algebraic(
                            (prev_board_status & (board_status ^ INVERSE_MASK))
                        )
                        print("Piece lifted: %s" % piece_coordinate)
                        board_state_piece_lifted = board_status
                        chessboard_led.show_legal_moves(piece_coordinate, game)
                    elif curr_pieces - num_pieces == 2:
                        capture_flag = True
                        print(
                            "Capture detected: %s"
                            % chessboard.coord_to_algebraic((board_state_piece_lifted & (board_status ^ INVERSE_MASK)))
                        )
                        board_state_capturing_piece = board_state_piece_lifted
                        board_state_captured_piece = board_status
                piece_diff = num_pieces - curr_pieces
                print(
                    "Piece diff: %s, Piece removed: %s, Capture detected: %s"
                    % (piece_diff, piece_removed, capture_flag)
                )

                print("board status: %s" % board_status)
                if board_status != prev_board_status and piece_diff == 0:
                    print("Piece moved")
                    move = chessboard.detect_move_positions(prev_board_status, board_status)
                    move_notation = "%s-%s" % move
                    original_position = move[0]
                    print("%s-%s" % move)
                    chessboard.update_board_move(move)
                    chessboard.print_board()
                    prev_board_status = board_status
                    piece_removed = False
                    capture_flag = False
                    board_state_piece_lifted = 0
                    board_state_capturing_piece = 0
                    board_state_captured_piece = 0
                    curr_pieces = num_pieces
                    position_changed_flag = False
                elif board_status != prev_board_status and piece_diff == -1 and capture_flag and piece_removed:
                    print("Piece captured")
                    move = chessboard.detect_capture_move_positions(
                        prev_board_status, board_state_capturing_piece, board_state_captured_piece
                    )
                    move_notation = "%sx%s" % move
                    original_position = move[0]
                    print("%sx%s" % move)
                    chessboard.update_board_move(move)
                    chessboard.print_board()
                    prev_board_status = board_status
                    piece_removed = False
                    capture_flag = False
                    board_state_piece_lifted = 0
                    board_state_capturing_piece = 0
                    board_state_captured_piece = 0
                    curr_pieces = num_pieces
                    position_changed_flag = False
                elif board_status == prev_board_status:
                    print("Piece moved back to original position")
                    move_notation = None
                    original_position = None
                    piece_removed = False
                    capture_flag = False
                    board_state_piece_lifted = 0
                    board_state_capturing_piece = 0
                    board_state_captured_piece = 0
                    curr_pieces = num_pieces
                    chessboard.print_board()
                    chessboard_led.clear_board()
                    position_changed_flag = False
        loop_counter += 1
        if game_in_progress:
            white_clock.update_clock()
            black_clock.update_clock()

        # If button 0 is pressed, drop to REPL
        if repl_button.value() == 0:
            print("Dropping to REPL")
            sys.exit()

        await uasyncio.sleep_ms(100)


async def initialize():
    global is_24h
    result = None

    print("Initializing Nextion...")
    # Flush buffer content before communicating with Nextion
    print("clearing the buffer content")
    buffer = uart.read()
    if buffer is not None:
        print("buffer: %s" % ubinascii.hexlify(buffer))
    await tft.send_command("bkcmd=3")
    await tft.set_value("splash.wifi_status.val", 1)
    await uasyncio.sleep(2)
    await tft.send_command("page main_menu")


def io_expander_callback(pin):
    global io_expander_interrupt_flag
    io_expander_interrupt_flag = True


def button_callback(pin):
    global button_interrupt_flag, button_interrupt_id
    button_interrupt_flag = True
    button_interrupt_id = pin


async def main():
    global uart, tft, sd_card_detect, sd_card_mounted
    global i2c, i2c_mux, chessboard, board, board_status
    global chessboard_led

    # Delay for three seconds to allow drop into REPL
    count = 0
    print("Starting in 3 seconds...")
    while count <= 15:
        # If button 0 is pressed, drop to REPL
        if repl_button.value() == 0:
            print("Dropping to REPL")
            sys.exit()

        # Do nothing
        count += 1
        await uasyncio.sleep_ms(200)

    # Set up SD Card if card is detected
    if not sd_card_detect.value():
        print("SD Card detected")
        sd = machine.SDCard(slot=2)
        if isinstance(sd, machine.SDCard):
            print("SD Card instance initialized")
            try:
                os.mount(sd, "/sd")
                print("SD Card mounted")
                print(os.listdir("/sd"))
                sd_card_mounted = True
            except OSError as e:
                print("SD Card mount failed: %s" % e)

    # Set up Wi-Fi connection
    await uasyncio.create_task(connect_wifi())

    # set up I2C multiplexer
    i2c = machine.I2C(0, scl=i2c_scl, sda=i2c_sda, freq=400000)
    i2c_mux_enable.off()
    await uasyncio.sleep_ms(100)
    i2c_mux_enable.on()
    i2c_mux = I2CMultiplex(i2c, i2c_mux_addr)
    i2c_mux.activate_channel(0)

    # Set up chessboard
    chessboard = Chessboard(i2c, chessboard_gpio_addr, led_strip)
    chessboard.read_board()
    board_status, board = chessboard.get_board()

    # Set up Chessboard LED strip
    chessboard_led = ChessboardLED(led_io=led_strip, vls_io=vls_enable)
    chessboard_led.clear_board()
    chessboard_led.show_occupied_squares(chessboard)

    # Set up interrupters
    # for io_interrupt_pin in io_interrupts:
    #     io_interrupt_pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=io_expander_callback)
    #     print("%s interrupt set up, current state: %s" % (io_interrupt_pin ,io_interrupt_pin.value()))

    # Set up interrupter for tactile switch
    button_white.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_callback)
    button_black.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_callback)

    # Create asynchronous co-routines

    uart = machine.UART(1, 115200, tx=17, rx=16)
    uart.init(115200, bits=8, parity=None, stop=1, rxbuf=2048, txbuf=2048)
    tft = nextion.Nextion(uart, lock, queue)

    await uasyncio.sleep(2)
    await uasyncio.create_task(initialize())

    loop = uasyncio.get_event_loop()
    try:
        loop.run_until_complete(event_listener())
    finally:
        loop.close()
