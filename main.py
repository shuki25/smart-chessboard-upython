import sys

import esp32
import machine
import network
import ntptime
import uasyncio
import ubinascii
import utime
import os

import nextion
import wifimgr
from primitives.queue import Queue
from neopixel import NeoPixel
from i2c_multiplex import I2CMultiplex
from io_expander import IOExpander
from chessboard import Chessboard, INVERSE_MASK
from chess_clock import ChessClock

# Constants
IO_EXPANDER_0_ADDRESS = 0x20
IO_EXPANDER_1_ADDRESS = 0x21
IO_EXPANDER_2_ADDRESS = 0x22
IO_EXPANDER_3_ADDRESS = 0x23
IO_EXPANDER_UI_ADDRESS = 0x24

# UI Buttons
BUTTON_W_RESIGN = 0x10
BUTTON_W_DRAW = 0x20
BUTTON_W_MOVE = 0x40
BUTTON_B_RESIGN = 0x100
BUTTON_B_DRAW = 0x200
BUTTON_B_MOVE = 0x400

# Initialization
i2c_mux_addr = 0x70
i2c: machine.I2C
i2c_mux: I2CMultiplex
ui_expander: IOExpander
chessboard_gpio_addr = [IO_EXPANDER_0_ADDRESS, IO_EXPANDER_1_ADDRESS, IO_EXPANDER_2_ADDRESS, IO_EXPANDER_3_ADDRESS]
chessboard: Chessboard
board: dict
board_status: int
sd_card_mounted = False
white_clock: ChessClock
black_clock: ChessClock

# Pin definitions
repl_button = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
i2c_mux_enable = machine.Pin(4, machine.Pin.OUT, machine.Pin.PULL_UP)
io_interrupt = machine.Pin(33, machine.Pin.IN, machine.Pin.PULL_UP)
led_strip = machine.Pin(15, machine.Pin.OUT)
sd_card_detect = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
i2c_sda = machine.Pin(21)
i2c_scl = machine.Pin(22)


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


async def wagtag_lightbar(pixel=32, period_ms=100):
    np = NeoPixel(led_strip, int(pixel))
    np.fill((0, 0, 0))
    np.write()

    ticks = 0

    while True:
        # if ticks % 16 == 0:
        #     for z in range(2):
        #         np.fill((0, 0, 0))
        #         np.write()
        #         await uasyncio.sleep_ms(period_ms)
        #         for i in range(0, 16):
        #             np[i] = (0, 0, 64)
        #         for i in range(16, 32):
        #             np[i] = (64, 0, 0)
        #         np.write()
        #         await uasyncio.sleep_ms(period_ms)
        #     np.fill((0, 0, 0))
        if ticks % 2 == 0:
            np.fill((0, 0, 0))
            np.write()
            await uasyncio.sleep_ms(50)
            for i in range(0, int(pixel / 2)):
                np[i] = (0, 0, 64)
            print("blue")
        else:
            np.fill((0, 0, 0))
            np.write()
            await uasyncio.sleep_ms(50)
            for i in range(int(pixel / 2), int(pixel)):
                np[i] = (64, 0, 0)
            print("red")
        np.write()
        ticks += 1
        await uasyncio.sleep_ms(period_ms)


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
    global tft, queue, lock, rtc
    global io_expander_interrupt_flag, chessboard, board, board_status, i2c, ui_expander
    global white_clock, black_clock, i2c_mux

    msg_count = 0
    loop_counter = 0
    is_display_sleeping = False
    prev_board_status = board_status
    prev_ui_state = ui_expander.read_input_port()
    ui_state = 0
    curr_pieces = 0
    board_state_piece_lifted = 0
    board_state_capturing_piece = 0
    board_state_captured_piece = 0
    game_in_progress = False

    chessboard.read_board()
    board_status, board = chessboard.get_board()
    curr_pieces = chessboard.count_pieces(board_status)
    capture_flag = False
    piece_removed = False
    position_changed_flag = False
    show_setup_message = False

    white_clock = ChessClock(i2c, i2c_mux, [0, 2])
    # black_clock = ChessClock(i2c, i2c_mux, [0, 3])

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
            show_setup_message = True
            white_clock.display_text("Set up board to", 0, 0)
            white_clock.display_text("starting position.", 0, 10, clear=False)
            await chessboard.reset_board_to_starting_position()
            white_clock.display_text("Ready to start.", 0, 0)
            white_clock.display_text("Press the button", 0, 10, clear=False)
            white_clock.display_text("to start game.", 0, 20, clear=False)

        if io_expander_interrupt_flag:
            io_expander_interrupt_flag = False
            ui_state = ui_expander.read_input_port()
            if ui_state != prev_ui_state:
                print("UI state changed")
                print("UI state: %s" % ui_state)
                if ui_state & BUTTON_W_RESIGN and game_in_progress:
                    print("Resign button pressed")
                    print("Resetting board positions")
                    await chessboard.reset_board_to_starting_position()
                if game_in_progress:
                    print("board state was reset")
                    piece_removed = False
                    capture_flag = False
                    board_state_piece_lifted = 0
                    board_state_capturing_piece = 0
                    board_state_captured_piece = 0
                    chessboard.read_board()
                    board_status, board = chessboard.get_board()
                    prev_board_status = board_status
                    curr_pieces = chessboard.count_pieces(board_status)
                    chessboard.print_board()
                else:
                    game_in_progress = True
                    white_clock.set_clock(90)
                    white_clock.start_clock()
            else:
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
                            print(
                                "Piece lifted: %s"
                                % chessboard.coord_to_algebraic((prev_board_status & (board_status ^ INVERSE_MASK)))
                            )
                            board_state_piece_lifted = board_status
                        elif curr_pieces - num_pieces == 2:
                            capture_flag = True
                            print(
                                "Capture detected: %s"
                                % chessboard.coord_to_algebraic(
                                    (board_state_piece_lifted & (board_status ^ INVERSE_MASK))
                                )
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
                        piece_removed = False
                        capture_flag = False
                        board_state_piece_lifted = 0
                        board_state_capturing_piece = 0
                        board_state_captured_piece = 0
                        curr_pieces = num_pieces
                        chessboard.print_board()
                        position_changed_flag = False
        loop_counter += 1
        if game_in_progress:
            white_clock.update_clock()

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


async def main():
    global uart, tft, sd_card_detect, sd_card_mounted
    global i2c, i2c_mux, chessboard, board, board_status, ui_expander

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

    # Set up Wifi connection
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

    # Set up UI devices
    ui_expander = IOExpander(i2c, IO_EXPANDER_UI_ADDRESS)
    ui_expander.polarity_inversion_port_0(0xFF)
    ui_expander.polarity_inversion_port_1(0xFF)
    ui_input = ui_expander.read_input_port()

    # Set up interrupters
    io_interrupt.irq(trigger=machine.Pin.IRQ_FALLING, handler=io_expander_callback)
    print("Interrupters set up, current state: %s" % io_interrupt.value())

    # Create asynchronous co-routines
    # uasyncio.create_task(wagtag_lightbar(32, 200))

    uart = machine.UART(1, 115200, tx=17, rx=16)
    uart.init(115200, bits=8, parity=None, stop=1, rxbuf=2048, txbuf=2048)
    tft = nextion.Nextion(uart, lock, queue)

    await uasyncio.sleep(2)
    await uasyncio.create_task(initialize())
    uasyncio.create_task(event_listener())

    while True:

        # If button 0 is pressed, drop to REPL
        if repl_button.value() == 0:
            print("Dropping to REPL")
            sys.exit()

        # Do nothing
        await uasyncio.sleep_ms(200)


uasyncio.run(main())
