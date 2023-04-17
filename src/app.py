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
from chess import Chess, algebraic_to_board_index
from chessboard import Chessboard, INVERSE_MASK, STARTING_POSITION
from chess_clock import ChessClock
from chessboard_led import ChessboardLED
from micropython import const
from als import AmbientLightSensor
from uci import UCI, parse_info


# Stockfish UCI engine Constants
# STOCKFISH_SERVER = "192.168.2.19"
STOCKFISH_SERVER = "10.42.0.1"
STOCKFISH_PORT = 9999

# Constants
IO_EXPANDER_0_ADDRESS = 0x20
IO_EXPANDER_1_ADDRESS = 0x21
IO_EXPANDER_2_ADDRESS = 0x22
IO_EXPANDER_3_ADDRESS = 0x23

# Game mode constants
MODE_VS_CPU = const(0)
MODE_VS_HUMAN = const(1)
MODE_VS_HUMAN_REMOTE = const(2)

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
vls_enable = machine.Pin(26, machine.Pin.OUT)
sd_card_detect = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
i2c_sda = machine.Pin(21)
i2c_scl = machine.Pin(22)

# I/O Expander Interrupts
io_interrupt = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)

# UI Tacile Buttons
button_black = machine.Pin(BUTTON_BLACK, machine.Pin.IN, machine.Pin.PULL_UP)
button_white = machine.Pin(BUTTON_WHITE, machine.Pin.IN, machine.Pin.PULL_UP)

# UART Serial communication
# print("setting up serial")
# uart = machine.UART(2, 115200, tx=17, rx=16)
# uart.deinit()
uart: machine.UART

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
light_sensor: AmbientLightSensor


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
            # await uasyncio.sleep_ms(200)
            #ntptime.settime()
            break
        # await uasyncio.sleep_ms(200)
    print("connected to wifi")
    print(wlan.ifconfig())


async def console_move_history(
    move_history, full_move_number, max_lines=13, game_over=False, result="*", page="game_progress"
):
    global tft

    print("in console_move_history")
    side = "b" if move_history[-1][1] == "" else "w"
    print("side: %s" % side)
    if len(move_history) >= max_lines:
        move_num = full_move_number - max_lines + 1
        if side == "w":
            max_lines -= 1
        history = move_history[-max_lines:]
    else:
        move_num = 1
        history = move_history
    console_buffer = ""

    print("move history: %s" % history)
    print("move number: %s" % move_num)

    for i, move in enumerate(history):
        if i > 0:
            console_buffer += "\\r"
        if move[1] != "":
            console_buffer += "%d. %s %s" % (move_num + i, move[0], move[1])
        else:
            if not game_over:
                console_buffer += "%d. %s ..." % (move_num + i, move[0])
            else:
                console_buffer += "%d. %s" % (move_num + i, move[0])
    if side == "w" and not game_over:
        console_buffer += "\\r%d. ..." % (move_num + i + 1)
    if game_over:
        console_buffer += "\\r%s" % result
    print("console buffer: %s" % console_buffer)
    await tft.print_console(console_buffer, page=page, max_lines=max_lines, replace=True)


async def event_listener():
    global tft, queue, lock, rtc, game
    global io_expander_interrupt_flag, chessboard, board, board_status, i2c
    global white_clock, black_clock, i2c_mux, button_interrupt_flag, button_interrupt_id

    msg_count = 0
    loop_counter = 0
    is_display_sleeping = False
    prev_board_status = board_status
    pre_move_board_state = STARTING_POSITION
    prev_ui_state = 0
    ui_state = 0
    curr_pieces = 0
    board_state_piece_lifted = 0
    board_state_capturing_piece = 0
    board_state_captured_piece = 0
    game_in_progress = False
    legal_moves = []
    potential_castle = False
    is_castling = False
    castling_side = None
    check_flag = False
    checkmate_flag = False
    stalemate_flag = False
    move_complete_flag = False
    opponent_move = False
    console_tag = "game_progress"
    cpu_2p_remote_mode = False
    cpu_2p_remote_side = None
    cpu_level = 3
    uci_player = None
    uci_player_wait_flag = False
    uci_move = None
    cpu_2p_remote_has_moved = True

    chessboard.read_board()
    board_status, board = chessboard.get_board()
    final_move_board_status = board_status
    final_num_pieces = chessboard.count_pieces(board_status)
    final_move = None
    curr_pieces = chessboard.count_pieces(board_status)
    simulated_board_status = board_status
    print("Initial board status: {}".format(board_status))
    capture_flag = False
    piece_removed = False
    position_changed_flag = False
    show_setup_message = False
    piece_coordinate = None
    move_notation = None
    legal_moves = []
    previous_position = None
    origin_square = None
    test_mode = False
    test_running = False
    in_game_mode = False
    game_mode = MODE_VS_HUMAN
    prev_lux = 0
    force_fix_board_flag = False
    fix_board_flag = False
    fix_board_setup_flag = False
    segoe_board = None
    update_led_board = False
    white_clock_time = 900
    black_clock_time = 900
    game_end_flag = False
    game_progress_page_id = 0

    white_clock.clear()
    black_clock.clear()
    game = Chess()

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

        # Parse Nextion events
        if event == nextion.TOUCH:
            (page, component, touch) = data
            print("Touch event: Page %s, Component %s, Touch %s" % data)

            # Go to main menu
            if page == 18 and component == 5:
                await tft.send_command("page main_menu")
                chessboard_led.clear_board()

            # Start game vs CPU
            if (page == 16 and component == 2) or (page == 16 and component == 15):
                game_mode = MODE_VS_CPU
                game_progress_page_id = 6
                in_game_mode = True
                game_in_progress = False
                show_setup_message = False
                cpu_2p_remote_mode = True
                uci_player_wait_flag = False
                cpu_2p_remote_has_moved = True
                print("CPU 2P remote mode: %s" % cpu_2p_remote_mode)
                cpu_2p_remote_side = "w" if component == 15 else "b"
                if cpu_2p_remote_side == "w":
                    white_clock_time = 600
                    black_clock_time = 900
                else:
                    white_clock_time = 900
                    black_clock_time = 600
                cpu_level = await tft.get_value("start_cpu.level.val")
                print("CPU level: %s" % cpu_level)
                await tft.send_command("page connect_cpu")
                chessboard_led.clear_board()
                if uci_player is None:
                    uci_player = UCI(STOCKFISH_SERVER, STOCKFISH_PORT)
                    await uci_player.start()
                else:
                    await uci_player.stop()
                    await uci_player.start()
                await tft.send_command("page board_setup")
                await tft.clear_console(page="gm_progress_c")

            # Start game vs human
            if page == 4 and component == 3:
                game_mode = MODE_VS_HUMAN
                game_progress_page_id = 7
                in_game_mode = True
                game_in_progress = False
                show_setup_message = False
                white_clock_time = 90
                black_clock_time = 90
                await tft.send_command("page board_setup")
                await tft.clear_console(page="game_progress")

            # Start game vs human remote
            if page == 4 and component == 5:
                game_mode = MODE_VS_HUMAN_REMOTE
                game_progress_page_id = 5
                in_game_mode = True
                await tft.send_command("page start_remote")

            # Run RGB LED strip test
            if page == 11 and component == 4:
                test_mode = 1
                print("Running RGB LED strip test")
                await chessboard_led.rgb_test(tft.print_console)

            # Fix board position
            if (page in [5, 6, 7] and component == 6):
                force_fix_board_flag = True

            # Fix board position completed
            if page == 14 and component == 5:
                print("Fix board position completed")
                fix_board_flag = False
                force_fix_board_flag = False
                print("Before fen parse")
                chessboard.print_board()
                chessboard.parse_fen(game.get_fen())
                print("After fen parse")
                chessboard.print_board()
                chessboard.read_board()
                board_status, board = chessboard.get_board()
                num_pieces = chessboard.count_pieces(board_status)
                print("Board status: %s" % board_status)
                prev_board_status = board_status
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
                chessboard_led.show_occupied_squares(chessboard)
                position_changed_flag = False
                potential_castle = False
                is_castling = False
                if game.turn == "w":
                    white_clock.start_clock()
                    black_clock.stop_clock()
                else:
                    white_clock.stop_clock()
                    black_clock.start_clock()

            # Start New Game - Same Game Mode
            if (page == 18 and component == 8) or (page == 7 and component == 10):
                print("Start new game")
                game = Chess()
                in_game_mode = True
                show_setup_message = False
                game_in_progress = False
                await tft.send_command("page board_setup")
                await tft.clear_console(page="game_progress")

            # Run OLED test
            if page == 11 and component == 5:
                test_mode = 2
                test_running = True
                print("Running OLED test")
                white_clock.clear()
                black_clock.clear()
                await tft.clear_console()
                await tft.print_console("Testing white OLED display...")
                white_clock.display_text("0123456789ABCDEF", 0, 0)
                white_clock.display_text("GHIJKLMNOPQRSTUVW", 0, 10, clear=False)
                white_clock.display_text("XYZ!@#$%^&*(){}',.", 0, 20, clear=False)
                await uasyncio.sleep_ms(2000)
                white_clock.clear()
                await tft.print_console("Done\\rTesting black OLED display...")
                black_clock.display_text("0123456789ABCDEF", 0, 0)
                black_clock.display_text("GHIJKLMNOPQRSTUVW", 0, 10, clear=False)
                black_clock.display_text("XYZ!@#$%^&*(){}',.", 0, 20, clear=False)
                await uasyncio.sleep_ms(2000)
                black_clock.clear()
                await tft.print_console("Done\\rTesting white clock...")
                white_clock.set_clock(10)
                white_clock.start_clock()
                if white_clock.is_clock_running():
                    print("White clock started")
                black_clock.set_clock(10)

            # Run ambient light sensor test
            if page == 11 and component == 6:
                test_mode = 3
                test_running = True
                white_clock.clear()
                black_clock.clear()
                lvl = light_sensor.lux_calc()
                await tft.clear_console()
                await tft.print_console("Shine bright light on the sensor")
                while lvl < 20000:
                    lvl = light_sensor.lux_calc()
                    await uasyncio.sleep_ms(100)
                await tft.print_console("\\rLuminosity: %s" % lvl)
                await tft.print_console("\\rCover the sensor with your finger")
                while lvl > 10:
                    lvl = light_sensor.lux_calc()
                    await uasyncio.sleep_ms(100)
                await tft.print_console("\\rLuminosity: %s" % lvl)
                await tft.print_console(
                    "\\rContinous luminosity measurement until\\ryou return to the previous screen."
                )
                prev_lux = lvl

            # Stop test mode
            if page == 12 and component == 3:
                test_mode = False
                white_clock.clear()
                black_clock.clear()

            # End game button pressed and resigned
            if page == 23 and component == 9:
                print("Player Resigned")
                await tft.send_command("page game_ended")

                await tft.set_value("t2.txt", "Resigned")
                if game.turn == "w":
                    await tft.set_value("t3.txt", "Black Wins")
                    chessboard_led.show_checkmate("w")
                    game.result = "0-1"
                else:
                    await tft.set_value("t3.txt", "White Wins")
                    chessboard_led.show_checkmate("b")
                    game.result = "1-0"
                game.game_over_flag = True
                await console_move_history(
                    game.get_move_history(),
                    game.fullmove,
                    max_lines=16,
                    game_over=game.game_over_flag,
                    result=game.result,
                    page="game_ended",
                )
                black_clock.stop_clock()
                white_clock.stop_clock()
                black_clock.clear()
                white_clock.clear()
                game_in_progress = False
                game_over_flag = True

            if page == 23 and component == 10:
                print("Game abandoned")
                if game_mode == MODE_VS_CPU:
                    await uci_player.stop()
                await tft.send_command("page main_menu")
                chessboard_led.clear_board()
                black_clock.stop_clock()
                white_clock.stop_clock()
                black_clock.clear()
                white_clock.clear()
                game_in_progress = False
                game_over_flag = True

        if event == nextion.TOUCH_IN_SLEEP:
            (page, component, touch) = data
            print("Touch in sleep event: Page %s, Component %s, Touch %s" % data)

        # Handle Fix Last Position Event
        if force_fix_board_flag and not fix_board_flag:
            if event != nextion.TOUCH:
                await tft.set_value("board_preview.prev_page.val", game_progress_page_id)
                await tft.send_command("page board_preview")
            print("Show Segoe chess board position on Nextion display")
            fix_board_flag = True
            force_fix_board_flag = False
            black_clock.stop_clock()
            white_clock.stop_clock()
            segoe_board = game.get_segoe_chess_board()
            print("Segoe board: %s" % segoe_board)
            await tft.set_value("board_preview.board.txt", segoe_board)
            chessboard.read_board()
            current_bitboard = chessboard.convert_bitboard_to_int()
            print("Translated bitboard: {}".format(current_bitboard))
            in_position_state = current_bitboard & pre_move_board_state
            out_position_state = ~current_bitboard & pre_move_board_state
            chessboard_led.zero_bitboard_squares()
            chessboard_led.prepare_bitboard_square(in_position_state, (0, 48, 0))
            chessboard_led.prepare_bitboard_square(out_position_state, (58, 0, 0))
            chessboard_led.display_bitboard_squares()

        # Perform test mode
        if test_mode == 2:  # OLED Display test
            if (
                white_clock.is_clock_expired()
                and not black_clock.is_clock_running()
                and not black_clock.is_clock_expired()
            ):
                white_clock.update_clock()
                await tft.print_console("Done\\rTesting black clock...")
                white_clock.stop_clock()
                black_clock.start_clock()
            elif black_clock.is_clock_expired() and test_running:
                black_clock.update_clock()
                black_clock.stop_clock()
                white_clock.clear()
                black_clock.clear()
                await tft.print_console("Done\\rTesting complete")
                test_running = False
            elif black_clock.is_clock_running():
                black_clock.update_clock()
            elif white_clock.is_clock_running():
                white_clock.update_clock()

        if test_mode == 3:  # ALS Sensor Test
            lvl = light_sensor.lux_calc()
            min_lvl = prev_lux / 1.05
            max_lvl = prev_lux * 1.05
            if lvl >= max_lvl or lvl <= min_lvl:
                print("max: %s, min: %s, lvl: %s" % (max_lvl, min_lvl, lvl))
                clock_text = "{:7.2f}".format(lvl)
                white_clock.display_time(clock_text, 0, 12, align="R")
            prev_lux = lvl
        elif test_mode == 4:  # Hall Effect Sensor Test
            pass

        if in_game_mode and fix_board_flag and io_expander_interrupt_flag:
            io_expander_interrupt_flag = False
            chessboard.read_board()
            current_bitboard = chessboard.convert_bitboard_to_int()
            print("Translated bitboard: {}".format(current_bitboard))
            in_position_state = current_bitboard & pre_move_board_state
            out_position_state = ~current_bitboard & pre_move_board_state
            chessboard_led.zero_bitboard_squares()
            chessboard_led.prepare_bitboard_square(in_position_state, (0, 48, 0))
            chessboard_led.prepare_bitboard_square(out_position_state, (58, 0, 0))
            chessboard_led.display_bitboard_squares()

        if in_game_mode and not fix_board_flag:
            if not game_in_progress and not show_setup_message:
                print("Set up the playing pieces on the board")
                show_setup_message = True
                white_clock.display_text("Board Setup", 0, 5)
                black_clock.display_text("Board Setup", 0, 5)
                prev_board_status, board = chessboard.get_board()
                chessboard_led.show_setup_squares(chessboard)
                io_expander_interrupt_flag = True
                while True:
                    if io_expander_interrupt_flag:
                        io_expander_interrupt_flag = False
                        chessboard.read_board()
                        board_status, board = chessboard.get_board()
                        if board_status != prev_board_status:
                            chessboard_led.show_setup_squares(chessboard)
                        if board_status == STARTING_POSITION:
                            chessboard_led.clear_board()
                            break
                    await uasyncio.sleep_ms(100)
                white_clock.clear()
                black_clock.display_text("Ready to start.", 0, 0)
                black_clock.display_text("Press the button", 0, 10, clear=False)
                black_clock.display_text("to start game.", 0, 20, clear=False)
                prev_board_status = board_status
                simulated_board_status = board_status
                move_complete_flag = False
                if game_mode == MODE_VS_HUMAN:
                    await tft.send_command("page game_progress")
                    await tft.clear_console(page="game_progress")
                    await tft.print_console("1. ...", page="game_progress")
                    console_tag = "game_progress"
                elif game_mode == MODE_VS_CPU:
                    await tft.send_command("page gm_progress_c")
                    await tft.clear_console(page="gm_progress_c")
                    await tft.print_console("1. ...", page="gm_progress_c")
                    await tft.clear_analysis(page="gm_progress_c")
                    console_tag = "gm_progress_c"
                elif game_mode == MODE_VS_HUMAN_REMOTE:
                    await tft.send_command("page gm_progress_r")
                    await tft.clear_console(page="gm_progress_r")
                    await tft.print_console("1. ...", page="gm_progress_r")
                    await tft.clear_analysis(page="gm_progress_r")
                    console_tag = "gm_progress_r"

            # Game in progress Logic starts here

            if game_in_progress and game_mode == MODE_VS_CPU:
                if game.turn == cpu_2p_remote_side and not uci_player_wait_flag:
                    fen = game.get_fen()
                    uci_player.go(fen, 15, 3000)
                    uci_player_wait_flag = True
                    cpu_2p_remote_has_moved = False
                    await tft.print_console(
                        "Thinking...", max_lines=9, page="gm_progress_c", txt_name="analysis", replace=True
                    )
                if game.turn == cpu_2p_remote_side and uci_player_wait_flag and not cpu_2p_remote_has_moved:
                    response = await uci_player.engine_response(["info", "bestmove"])
                    if response.startswith("bestmove"):
                        cpu_2p_remote_has_moved = True
                        uci_move = response.split(" ")[1]
                        cpu_move = "CPU move: {}".format(uci_move)
                        print(cpu_move)
                        await tft.print_console(cpu_move + "\\r", max_lines=9, page="gm_progress_c", txt_name="analysis")
                        chessboard_led.show_interim_move(uci_move, cpu_2p_remote_side)
                    else:
                        try:
                            info = parse_info(response)
                            if "score" in info:
                                analysis = "Depth: %s Score: %s\\r%s\\r" % (info["depth"], info["score"], info["pv"])
                                await tft.print_console(analysis, max_lines=9, page="gm_progress_c", txt_name="analysis")
                        except ValueError:
                            pass
                if game.turn == cpu_2p_remote_side and uci_player_wait_flag and cpu_2p_remote_has_moved:
                    pass

            # Handle button interrupts

            if button_interrupt_flag:
                button_interrupt_flag = False

                if (not button_white.value() and not button_black.value() and game_in_progress) or (
                    not button_black.value() and not game_in_progress
                ):
                    if not button_white.value() and not button_black.value():
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
                    if not button_black.value() and button_white.value():
                        game_in_progress = True
                        game.reset_board()
                        update_led_board = True
                        print("turn: {}".format(game.turn))
                        white_clock.set_clock(white_clock_time)
                        white_clock.start_clock()
                        black_clock.set_clock(black_clock_time)
                elif game_in_progress:
                    if not button_white.value() and game.turn == "w":
                        print("White button pressed")
                        white_clock.stop_clock()
                        if move_complete_flag:
                            prev_board_status = board_status
                            piece_removed = False
                            capture_flag = False
                            board_state_piece_lifted = 0
                            board_state_capturing_piece = 0
                            board_state_captured_piece = 0
                            curr_pieces = final_num_pieces
                            position_changed_flag = False
                            if potential_castle and is_castling:
                                chessboard.update_castling_move(game.turn, castling_side)
                                potential_castle = False
                                is_castling = False
                                castling_side = None
                            else:
                                chessboard.update_board_move(final_move)
                            final_move = None
                            move_complete_flag = False
                            chessboard_led.clear_board()
                            game.make_move(move_notation, side="w")
                            update_led_board = True
                            pre_move_board_state = chessboard.convert_bitboard_to_int()
                            if game_mode == MODE_VS_CPU:
                                if game.turn == cpu_2p_remote_side:
                                    uci_player_wait_flag = False
                                    cpu_2p_remote_has_moved = False
                            await console_move_history(
                                game.get_move_history(),
                                game.fullmove,
                                max_lines=16,
                                game_over=game.game_over_flag,
                                result=game.result,
                                page=console_tag,
                            )
                            if game_mode != MODE_VS_CPU or (game_mode == MODE_VS_CPU and cpu_2p_remote_side == "w"):
                                black_clock.add_clock_countdown(5)
                            black_clock.start_clock()
                            move_complete_flag = False
                        else:
                            print("Incomplete move")
                            white_clock.start_clock()
                            chessboard_led.clear_board()
                    elif not button_black.value() and game.turn == "b":
                        print("Black button pressed")
                        black_clock.stop_clock()
                        if move_complete_flag:
                            prev_board_status = board_status
                            piece_removed = False
                            capture_flag = False
                            board_state_piece_lifted = 0
                            board_state_capturing_piece = 0
                            board_state_captured_piece = 0
                            curr_pieces = final_num_pieces
                            chessboard_led.show_interim_move(move_notation, game.turn)
                            position_changed_flag = False
                            if potential_castle and is_castling:
                                chessboard.update_castling_move(game.turn, castling_side)
                                potential_castle = False
                                is_castling = False
                                castling_side = None
                            else:
                                chessboard.update_board_move(final_move)
                            final_move = None
                            move_complete_flag = False
                            chessboard_led.clear_board()
                            game.make_move(move_notation, side="b")
                            update_led_board = True
                            black_clock.stop_clock()
                            pre_move_board_state = chessboard.convert_bitboard_to_int()
                            if game_mode == MODE_VS_CPU:
                                if game.turn == cpu_2p_remote_side:
                                    uci_player_wait_flag = False
                                    cpu_2p_remote_has_moved = False
                            await console_move_history(
                                game.get_move_history(),
                                game.fullmove,
                                max_lines=16,
                                game_over=game.game_over_flag,
                                result=game.result,
                                page=console_tag,
                            )
                            if game_mode != MODE_VS_CPU or (game_mode == MODE_VS_CPU and cpu_2p_remote_side == "b"):
                                white_clock.add_clock_countdown(5)
                            white_clock.start_clock()
                        else:
                            print("Incomplete move")
                            black_clock.start_clock()
                            chessboard_led.clear_board()
                    chessboard.print_board()
                    print("turn: {}".format(game.turn))
                    print(game)

            # Simulate io_expander interrupt (due to errorenous pin assignment in schematic)
            # is triggered when a piece is lifted from the board by polling the board positions
            # every 100ms

            # chessboard.read_board()
            # board_status, board = chessboard.get_board()
            # if board_status != simulated_board_status:
            #     io_expander_interrupt_flag = True
            #     simulated_board_status = board_status
            #     print("Simulated IO Expander interrupt")

            if io_expander_interrupt_flag and game_in_progress:
                io_expander_interrupt_flag = False
                print("IO Expander interrupt")
                chessboard.read_board()
                board_status, board = chessboard.get_board()

                delta_positions = chessboard.delta_board_positions(prev_board_status, board_status)
                print("delta_positions: %d" % delta_positions)

                if delta_positions > 1:
                    if potential_castle and delta_positions <= 4:
                        print("More than two positions changed, but castling is possible")
                    elif delta_positions == 2 and capture_flag:
                        print("Two positions changed, capture is possible")
                    elif delta_positions > 2:
                        print("More than two positions changed, force board reconfiguration")
                        force_fix_board_flag = True

                if not position_changed_flag and board_status != prev_board_status and not force_fix_board_flag:
                    position_changed_flag = True
                    print("board position changed")

                if position_changed_flag and not force_fix_board_flag:
                    num_pieces = chessboard.count_pieces(board_status)
                    if num_pieces < curr_pieces:

                        # First piece lifted

                        if curr_pieces - num_pieces == 1 and is_castling and potential_castle:
                            print("Rook moved during castling")
                        elif curr_pieces - num_pieces == 1 and move_complete_flag and not capture_flag:
                            piece_coordinate = chessboard.coord_to_algebraic(
                                (final_move_board_status & (board_status ^ INVERSE_MASK))
                            )
                            print("Piece lifted: %s, Current move: %s, Origin square: %s" % (piece_coordinate, final_move, origin_square))
                            if piece_coordinate == final_move[1]:
                                chessboard_led.show_legal_moves(final_move[0], legal_moves, game)
                            else:
                                chessboard_led.show_illegal_piece_lifted(piece_coordinate, game)
                        elif curr_pieces - num_pieces == 1 and not capture_flag and not move_complete_flag:
                            piece_removed = True
                            piece_coordinate = chessboard.coord_to_algebraic(
                                (prev_board_status & (board_status ^ INVERSE_MASK))
                            )
                            print("Piece lifted: %s" % piece_coordinate)
                            board_state_piece_lifted = board_status
                            index = chessboard.algebraic_to_board_index(piece_coordinate)
                            piece_identifier = game.identify_piece(piece_coordinate)
                            piece_status = game.is_friendly(index, game.turn)
                            if piece_identifier in "Kk":
                                print("King lifted")
                                if game.can_king_castle(game.turn):
                                    print("Potential Castle")
                                    potential_castle = True
                                else:
                                    print("No potential castle")
                                    potential_castle = False

                            if game_mode == MODE_VS_CPU and game.turn == cpu_2p_remote_side and uci_player_wait_flag and cpu_2p_remote_has_moved:
                                if piece_coordinate[:2] == uci_move[:2]:
                                    print("Piece lifted matches CPU move")
                                    chessboard_led.show_cpu_remote_move(uci_move, game.turn)
                                else:
                                    print("Piece lifted does not match CPU move")
                                    chessboard_led.show_illegal_piece_lifted(piece_coordinate, game)
                            elif piece_status:
                                print("Friendly piece lifted")
                                origin_square = algebraic_to_board_index(piece_coordinate)
                                legal_moves = game.get_legal_moves(origin_square)
                                chessboard_led.show_legal_moves(piece_coordinate, legal_moves, game)
                            else:
                                print("Enemy piece lifted")
                                chessboard_led.show_illegal_piece_lifted(piece_coordinate, game)

                        # Second piece lifted
                        elif curr_pieces - num_pieces == 2 and move_complete_flag and capture_flag:
                            piece_coordinate = chessboard.coord_to_algebraic(
                                (final_move_board_status & (board_status ^ INVERSE_MASK))
                            )
                            print("Piece lifted: %s" % piece_coordinate)
                            chessboard_led.show_illegal_piece_lifted(piece_coordinate, game)
                        elif curr_pieces - num_pieces == 2:
                            print("Two pieces lifted")
                            piece_coordinate = chessboard.coord_to_algebraic(
                                (board_state_piece_lifted & (board_status ^ INVERSE_MASK))
                            )
                            print("Piece lifted: %s" % piece_coordinate)
                            if piece_coordinate is None:
                                print("Unknown piece lifted, bailing")
                                force_fix_board_flag = True
                            else:
                                index = chessboard.algebraic_to_board_index(piece_coordinate)
                                piece_status = game.is_friendly(index, game.turn)
                                if piece_status:
                                    print("Friendly piece lifted")
                                else:
                                    print("Enemy piece lifted")

                                if potential_castle and piece_coordinate is not None:
                                    board_state_piece_lifted = board_status
                                    index = chessboard.algebraic_to_board_index(piece_coordinate)
                                    piece_identifier = game.identify_piece(piece_coordinate)
                                    if piece_identifier in "Rr":
                                        print("The king is castling")
                                        is_castling = True
                                        if index in [7, 63]:
                                            print("King side castle")
                                            castling_side = "K"
                                        elif index in [0, 56]:
                                            print("Queen side castle")
                                            castling_side = "Q"
                                        else:
                                            print("Invalid castle")
                                            castling_side = None
                                    print("Action ignored")
                                elif piece_status:
                                    print("Two friendly pieces lifted, bail out")
                                    chessboard_led.show_illegal_piece_lifted(piece_coordinate, game)
                                elif not piece_status:
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
                        "Piece diff: %s, Piece removed: %s, Capture detected: %s, Potential castle: %s, Is castling: %s, move_complete_flag: %s, game_mode: %s"
                        % (piece_diff, piece_removed, capture_flag, potential_castle, is_castling, move_complete_flag, game_mode)
                    )

                    print("board status: %s" % board_status)
                    if board_status != prev_board_status and piece_diff == 0:
                        is_legal_move = False
                        if game_mode == MODE_VS_CPU and game.turn == cpu_2p_remote_side and uci_player_wait_flag and cpu_2p_remote_has_moved:
                            move = chessboard.detect_move_positions(prev_board_status, board_status)
                            if potential_castle and is_castling:
                                if chessboard.check_castling_positions(game.turn, castling_side, board_status):
                                    is_legal_move = True
                            elif uci_move[2:] == move[1]:
                                print("Move matches CPU move")
                                is_legal_move = True
                            else:
                                print("Move does not match CPU move")
                                chessboard_led.show_illegal_piece_lifted(piece_coordinate, game)
                        else:
                            if potential_castle and is_castling:
                                if chessboard.check_castling_positions(game.turn, castling_side, board_status):
                                    is_legal_move = True
                            else:
                                move = chessboard.detect_move_positions(prev_board_status, board_status)
                                move_notation = "%s-%s" % move
                                if move_notation in legal_moves:
                                    print("Move is legal")
                                    is_legal_move = True
                                else:
                                    print("Move is illegal")
                                    chessboard_led.show_illegal_piece_lifted(piece_coordinate, game)
                        if is_legal_move:
                            print("Move completed")
                            move_complete_flag = True
                            if potential_castle and is_castling:
                                print("Move recognized as castling")
                                if chessboard.check_castling_positions(game.turn, castling_side, board_status):
                                    move_notation = "O-O" if castling_side == "K" else "O-O-O"
                                    print("move: %s" % move_notation)
                                    print("Waiting for button press to confirm move")
                                    final_move_board_status = board_status
                                    final_num_pieces = num_pieces
                                    final_move = chessboard.get_castling_move(game.turn, castling_side)
                                    # chessboard_led.show_interim_move(move_notation, game.turn)
                                    # chessboard.update_castling_move(game.turn, castling_side)
                                    # potential_castle = False
                                    # is_castling = False
                                    # castling_side = None
                            else:
                                move = chessboard.detect_move_positions(prev_board_status, board_status)
                                move_notation = "%s-%s" % move
                                original_position = move[0]
                                print("%s-%s" % move)
                                print("Waiting for button press to confirm move")
                                final_move_board_status = board_status
                                final_num_pieces = num_pieces
                                final_move = move
                                chessboard_led.show_interim_move(move_notation, game.turn)
                    elif board_status != prev_board_status and piece_diff == -1 and capture_flag and piece_removed:
                        print("Piece captured")
                        move = chessboard.detect_capture_move_positions(
                            prev_board_status, board_state_capturing_piece, board_state_captured_piece
                        )
                        move_notation = "%sx%s" % move
                        original_position = move[0]
                        print("%sx%s" % move)
                        print("Waiting for button press to confirm move")
                        final_move_board_status = board_status
                        final_num_pieces = num_pieces
                        final_move = move
                        chessboard_led.show_interim_move(move_notation, game.turn)
                        move_complete_flag = True
                    elif board_status == prev_board_status:
                        print("Piece moved back to original position")
                        move_complete_flag = False
                        final_move_board_status = board_status
                        final_num_pieces = num_pieces
                        final_move = None
                        move_notation = None
                        original_position = None
                        piece_removed = False
                        capture_flag = False
                        board_state_piece_lifted = 0
                        board_state_capturing_piece = 0
                        board_state_captured_piece = 0
                        curr_pieces = num_pieces
                        chessboard.print_board()
                        position_changed_flag = False
                        potential_castle = False
                        is_castling = False
                        if game_mode == MODE_VS_CPU and game.turn == cpu_2p_remote_side and uci_player_wait_flag and cpu_2p_remote_has_moved:
                            chessboard_led.show_interim_move(uci_move, game.turn)
                        else:
                            chessboard_led.show_occupied_squares(chessboard)
            loop_counter += 1
            if game_in_progress:
                if white_clock.is_clock_expired():
                    print("White clock expired")
                    await tft.send_command("page game_ended")
                    await tft.set_value("t2.txt", "Time Expired")
                    await tft.set_value("t3.txt", "Black Wins")
                    chessboard_led.show_checkmate("w")
                    game_in_progress = False
                    game_over_flag = True
                elif black_clock.is_clock_expired():
                    print("Black clock expired")
                    await tft.send_command("page game_ended")
                    await tft.set_value("t2.txt", "Time Expired")
                    await tft.set_value("t3.txt", "White Wins")
                    chessboard_led.show_checkmate("b")
                    game_in_progress = False
                    game_over_flag = True
                elif game.checkmate_flag:
                    print("Checkmate detected")
                    await tft.send_command("page game_ended")
                    await tft.set_value("t2.txt", "Checkmate")
                    winner = "White" if game.turn == "b" else "Black"
                    await tft.set_value("t3.txt", "%s Wins" % winner)
                    chessboard_led.show_checkmate(game.turn)
                    game_in_progress = False
                    checkmate_flag = False
                    game_over_flag = True
                elif game.stalemate_flag:
                    print("Stalemate detected")
                    await tft.send_command("page game_ended")
                    await tft.set_value("t2.txt", "Stalemate")
                    await tft.set_value("t3.txt", "Game Ends in Draw")
                    chessboard_led.show_stalemate()
                    game_in_progress = False
                    stalemate_flag = False
                    game_over_flag = True
                else:
                    if update_led_board:
                        chessboard_led.show_occupied_squares(chessboard)
                        update_led_board = False
                    white_clock.update_clock()
                    black_clock.update_clock()

            # If button 0 is pressed, drop to REPL
            if repl_button.value() == 0:
                print("Dropping to REPL")
                sys.exit()

        # Update luminosity
        lvl = light_sensor.lux_calc()
        min_lvl = prev_lux / 1.05
        max_lvl = prev_lux * 1.05
        if lvl >= max_lvl or lvl <= min_lvl:
            chessboard_led.set_lux(lvl)
        prev_lux = lvl

        await uasyncio.sleep_ms(50)


async def initialize():
    global is_24h, wifi_connected, tft
    result = None

    print("Initializing Nextion...")
    # Flush buffer content before communicating with Nextion
    print("clearing the buffer content")
    buffer = uart.read()
    if buffer is not None:
        print("buffer: %s" % ubinascii.hexlify(buffer))
    await tft.send_command("bkcmd=3")
    await tft.set_value("splash.wifi_status.val", 1 if wifi_connected else 0)
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
    global chessboard_led, white_clock, black_clock, light_sensor

    # # Delay for three seconds to allow drop into REPL
    # count = 0
    # print("Starting in 3 seconds...")
    # while count <= 15:
    #     # If button 0 is pressed, drop to REPL
    #     if repl_button.value() == 0:
    #         print("Dropping to REPL")
    #         sys.exit()
    #
    #     # Do nothing
    #     count += 1
    #     await uasyncio.sleep_ms(200)

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

    # set up I2C multiplexer
    i2c = machine.I2C(0, scl=i2c_scl, sda=i2c_sda, freq=400000)
    i2c_mux_enable.off()
    await uasyncio.sleep_ms(100)
    i2c_mux_enable.on()
    i2c_mux = I2CMultiplex(i2c, i2c_mux_addr)
    i2c_mux.activate_channel(0)

    # Set up Chess Clocks
    white_clock = ChessClock(i2c, i2c_mux, [0, 3])
    black_clock = ChessClock(i2c, i2c_mux, [0, 2])
    white_clock.display_text("Please wait...", y=12)
    black_clock.display_text("Please wait...", y=12)

    # Set up Wi-Fi connection
    await uasyncio.create_task(connect_wifi())

    # Set up chessboard
    chessboard = Chessboard(i2c, chessboard_gpio_addr, led_strip)
    chessboard.read_board()
    board_status, board = chessboard.get_board()

    # Set up ambient light sensor
    light_sensor = AmbientLightSensor(i2c)
    lux_value = light_sensor.lux_calc()
    print("Current ambient lumiosity level: %d" % lux_value)

    # Set up Chessboard LED strip
    print("Setting up LED strip")
    chessboard_led = ChessboardLED(led_io=led_strip, vls_io=vls_enable)
    chessboard_led.set_lux(lux_value)
    print("LED strip setup complete")
    print("LED clear")
    chessboard_led.clear_board()
    print("LED show occupied squares")
    chessboard_led.show_occupied_squares(chessboard)

    # Set up interrupters
    io_interrupt.irq(trigger=machine.Pin.IRQ_FALLING, handler=io_expander_callback)
    print("%s interrupt set up, current state: %s" % (io_interrupt, io_interrupt.value()))

    # Set up interrupter for tactile switch
    button_white.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_callback)
    button_black.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_callback)
    print("button interrupt callbacks are set up")

    # Create asynchronous co-routines

    uart = machine.UART(1, 115200, tx=33, rx=32)
    uart.init(115200, bits=8, parity=None, stop=1, rxbuf=1024, txbuf=1024)
    print("UART initialized")
    tft = nextion.Nextion(uart, lock, queue)
    print("Nextion instance created")

    await uasyncio.sleep(2)
    print("Performing initialization")
    await uasyncio.create_task(initialize())
    print("Initialization complete")

    print("Starting main loop")
    loop = uasyncio.get_event_loop()
    try:
        loop.run_until_complete(event_listener())
    finally:
        loop.close()
