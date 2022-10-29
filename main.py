import sys

import esp32
import machine
import network
import ntptime
import uasyncio
import ubinascii
import utime

import nextion
import wifimgr
from primitives.queue import Queue
from neopixel import NeoPixel 

# Initialization

# Pin definitions
repl_button = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
red_led = machine.Pin(5, machine.Pin.OUT)
green_led = machine.Pin(18, machine.Pin.OUT)
blue_led = machine.Pin(2, machine.Pin.OUT)
optical_encoder = machine.Pin(4, machine.Pin.IN, machine.Pin.PULL_UP)
hopper_motor_relay = machine.Pin(12, machine.Pin.OUT)
led_strip = machine.Pin(2, machine.Pin.OUT)

# UART Serial communication
print("setting up serial")
uart = machine.UART(1, 115200)
uart.deinit()

# Uasyncio lock object
lock = uasyncio.Lock()

# Initialize Queue for synchronizing UART messages
queue = Queue()

# Nextion display
tft = None

# Initialize variables
wifi_connected = 0
# wlan = network.WLAN(network.STA_IF)
wlan = None
rtc = machine.RTC()
is_24h = False
device_id = ubinascii.hexlify(machine.unique_id())
hopper_ticks = 0
previous_tick = 0


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
            for i in range(0, int(pixel/2)):
                np[i] = (0, 0, 64)
        else:
            np.fill((0, 0, 0))
            np.write()
            await uasyncio.sleep_ms(50)
            for i in range(int(pixel/2), int(pixel)):
                np[i] = (64, 0, 0)
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
    wlan = wifimgr.get_connection()

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


async def nextion_monitor():
    global tft
    global queue
    global lock
    global rtc

    msg_count = 0
    loop_counter = 0
    cpu_temp_max = 0.0
    cpu_temp_min = 100.0
    is_display_sleeping = False

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

        if loop_counter % 20 == 0:
            tf = esp32.raw_temperature()
            tc = (tf - 32.0) / 1.8
            cpu_temp = float("{0:3.1f}".format(tc))
            if cpu_temp > cpu_temp_max:
                cpu_temp_max = cpu_temp
                await tft.set_value("page7.cpu_temp_max.txt", "%s" % cpu_temp)
            if cpu_temp < cpu_temp_min:
                cpu_temp_min = cpu_temp
                await tft.set_value("page7.cpu_temp_min.txt", "%s" % cpu_temp)

        loop_counter += 1

        await uasyncio.sleep_ms(200)


async def initialize():
    global is_24h
    result = None

    print("Initializing...")
    # Flush buffer content before communicating with Nextion
    print("clearing the buffer content")
    buffer = uart.read()
    if buffer is not None:
        print("buffer: %s" % ubinascii.hexlify(buffer))
    await tft.send_command("bkcmd=3")
    try:
        result = await tft.get_value("page0.flag_24h.val")
        is_24h = True if result else False

    except AssertionError as e:
        print(e)
    print("value: %s" % result)
    await tft.set_value("page0.flag_connected.val", 1)
    await uasyncio.sleep(2)
    await tft.send_command("page page1")


def encoder_callback(pin):
    global hopper_ticks
    global previous_tick

    if pin.value() != previous_tick:
        hopper_ticks += 1
        print("Encoder ticked. Ticker counter: %d" % hopper_ticks)
    previous_tick = pin.value()


async def dispense_food(encoder_ticks):
    global hopper_ticks

    start_ticks = hopper_ticks
    target_ticks = start_ticks + encoder_ticks

    hopper_motor_relay.on()
    while hopper_ticks < target_ticks:
        await uasyncio.sleep_ms(200)
    hopper_motor_relay.off()


async def main():
    global uart
    global tft

    # Delay for two seconds to allow ampy to drop into REPL
    count = 0
    while count <= 15:
        blue_led.on()
        # If button 0 is pressed, drop to REPL
        if repl_button.value() == 0:
            for i in range(2):
                blue_led.off()
                await uasyncio.sleep_ms(200)
                blue_led.on()
                await uasyncio.sleep_ms(200)
            blue_led.off()
            print("Dropping to REPL")
            sys.exit()

        # Do nothing
        count += 1
        await uasyncio.sleep_ms(200)

    blue_led.off()

    # Set up Wifi connection
    await uasyncio.create_task(connect_wifi())

    # Set up interrupters
    optical_encoder.irq(trigger=machine.Pin.IRQ_FALLING, handler=encoder_callback)

    # Create asynchronous co-routines
    uasyncio.create_task(wagtag_lightbar(32, 200))
    # uasyncio.create_task(blink(red_led, 750))
    # uasyncio.create_task(wifi_blink(blue_led, 250))
    # uasyncio.create_task(blink(green_led, 500))

    # uart = machine.UART(1, 115200)
    # uart.init(115200, bits=8, parity=None, stop=1, rxbuf=2048, txbuf=2048)
    # tft = nextion.Nextion(uart, lock, queue)

    # await uasyncio.sleep(5)
    # await uasyncio.create_task(initialize())
    # uasyncio.create_task(nextion_monitor())

    while True:

        # If button 0 is pressed, drop to REPL
        if repl_button.value() == 0:
            for i in range(2):
                blue_led.off()
                await uasyncio.sleep_ms(200)
                blue_led.on()
                await uasyncio.sleep_ms(200)
            blue_led.off()
            red_led.off()
            green_led.off()
            print("Dropping to REPL")
            sys.exit()

        # Do nothing
        await uasyncio.sleep_ms(200)


uasyncio.run(main())
