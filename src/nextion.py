import struct

import machine
import uasyncio
import ubinascii
import struct

from primitives.queue import Queue

# Event Types
TOUCH = 0x65  # Touch event
TOUCH_COORDINATE = 0x67  # Touch coordinate
TOUCH_IN_SLEEP = 0x68  # Touch event in sleep mode
AUTO_SLEEP = 0x86  # Device automatically enters into sleep mode
AUTO_WAKE = 0x87  # Device automatically wake up
STARTUP = 0x88  # System successful start up
SD_CARD_UPGRADE = 0x89  # Start SD card upgrade

# Response Types
STRING = 0x70
NUMBER = 0x71
PAGE = 0x66
INVALID_VARIABLE = 0x1A
SUCCESS = 0x01

# End of transmission
EOL = b"\xff\xff\xff"

# Nextion response packet sizes
PACKET_LENGTH_MAP = {
    0x00: 6,  # Nextion Startup
    0x01: 4,  # Success
    0x1A: 4,  # Invalid Variable
    0x24: 4,  # Serial Buffer Overflow
    0x65: 7,  # Touch Event
    0x66: 5,  # Current Page Number
    0x67: 9,  # Touch Coordinate(awake)
    0x68: 9,  # Touch Coordinate(sleep)
    0x71: 8,  # Numeric Data Enclosed
    0x86: 4,  # Auto Entered Sleep Mode
    0x87: 4,  # Auto Wake from Sleep
    0x88: 4,  # Nextion Ready
    0x89: 4,  # Start microSD Upgrade
    0xFD: 4,  # Transparent Data Finished
    0xFE: 4,  # Transparent Data Ready
}

# Nextion Console
CONSOLE_BUFFER_SIZE = 512
CONSOLE_MAX_LINES = 11


def rawbytes(s):
    """Convert a string to raw bytes without encoding"""
    outlist = []
    for cp in s:
        num = ord(cp)
        if num < 255:
            outlist.append(struct.pack("B", num))
        elif num < 65535:
            outlist.append(struct.pack(">H", num))
        else:
            b = (num & 0xFF0000) >> 16
            H = num & 0xFFFF
            outlist.append(struct.pack(">bH", b, H))
    return b"".join(outlist)


class Nextion:

    uart = None
    lock = None
    queue = None
    console_buffer = []

    def __init__(self, uart, lock, queue):
        if isinstance(uart, machine.UART):
            self.uart = uart
        elif uart is None:
            raise Exception("uart parameter is required")
        else:
            raise Exception("uart is not an UART object")

        if isinstance(lock, uasyncio.Lock):
            self.lock = lock
        elif lock is None:
            raise Exception("lock parameter is required")
        else:
            raise Exception("lock is not an uasyncio.Lock object")

        if isinstance(queue, Queue):
            self.queue = queue
        elif queue is None:
            raise Exception("queue parameter is required")
        else:
            raise Exception("queue is not primitives.queue object")

    async def flush_buffer(self):
        if self.uart.any() > 0:
            buffer = self.uart.read()
            msg = buffer.split(EOL)
            for i, row in enumerate(msg):
                if len(row):
                    self.queue.put_nowait(row + EOL)

    async def clear_console(self, page="test_monitor"):
        self.console_buffer = []
        variable_name = "%s.console.txt" % page
        await self.set_value(variable_name, "")

    async def clear_analysis(self, page="test_monitor"):
        variable_name = "%s.analysis.txt" % page
        await self.set_value(variable_name, "")

    async def print_console(
        self,
        s,
        clear=False,
        max_lines=CONSOLE_MAX_LINES,
        buffer_size=CONSOLE_BUFFER_SIZE,
        page="test_monitor",
        txt_name="console",
        replace=False,
    ):
        if clear:
            await self.clear_console()
            return

        if not replace:
            buffer = s.split("\\r")
            if len(buffer) > 1:
                for i, row in enumerate(buffer):
                    if i == 0 and len(self.console_buffer) > 0:
                        self.console_buffer[-1] += row
                    else:
                        self.console_buffer.append(row)
            else:
                self.console_buffer.append(s)

            while len(self.console_buffer) >= max_lines:
                self.console_buffer.pop(0)
            console_buffer = "\\r".join(self.console_buffer)
        else:
            console_buffer = s

        if len(console_buffer) > buffer_size:
            console_buffer = console_buffer[-buffer_size:]

        print("Printing to console: %s" % s)
        variable_name = "%s.%s.txt" % (page, txt_name)
        await self.set_value(variable_name, console_buffer)

    async def send_command(self, command):
        prepare_command = b"%s" % command + EOL
        await self.lock.acquire()
        await self.flush_buffer()
        print("Command executed: %s" % command)
        self.uart.write(prepare_command)
        response = None
        a = 0
        while a < 3:
            await uasyncio.sleep_ms(100)
            if self.uart.any() > 0:
                response = self.uart.read()
                print("command response: %s " % response)
                break
            a += 1
        self.lock.release()

        return response

    async def get_value(self, key):
        prepare_command = b"get %s" % key + EOL
        await self.lock.acquire()
        await self.flush_buffer()
        self.uart.write(prepare_command)
        response = None
        value = None
        a = 0
        while a < 3:
            await uasyncio.sleep_ms(100)
            if self.uart.any() > 0:
                response = self.uart.read()
                print(response)
                break
            a += 1
        self.lock.release()
        if response is None:
            print("get_value timed out")
        else:
            typ = response[0]
            raw = response[1:]
            if typ == INVALID_VARIABLE:
                raise AssertionError("Invalid variable: %s" % key)
            elif typ == NUMBER and len(response) == PACKET_LENGTH_MAP[typ]:
                print("got number response")
                value = struct.unpack("i", raw)[0]
            elif typ == STRING:
                print("got string response")
                value = raw.decode("iso-8859-1")
            elif typ == PAGE:
                print("got page response")
                value = raw[1]
            else:
                print("got unknown data: %s", ubinascii.hexlify(response))

            print("%s: %s" % (key, response))
        return value

    async def set_value(self, key, value):
        print("value type: %s" % type(value))
        if isinstance(value, str):
            out_value = bytearray(b'"' + rawbytes(value) + b'"')
        elif isinstance(value, float):
            print("Float is not supported. Converting to string")
            out_value = '"%s"' % str(value)
        elif isinstance(value, int):
            out_value = str(value)
        else:
            raise AssertionError('value type "%s" is not supported for set' % type(value).__name__)

        prepare_command = bytearray(key.encode("iso-8859-1") + b"=") + out_value + EOL
        await self.lock.acquire()
        await self.flush_buffer()
        self.uart.write(prepare_command)
        response = None
        status = None
        a = 0
        while a < 3:
            await uasyncio.sleep_ms(100)
            if self.uart.any() > 0:
                response = self.uart.read()
                print("set_value response: %s" % response)
                break
            a += 1
        self.lock.release()

        if response is None:
            status = SUCCESS
            print("%s success" % prepare_command)
        else:
            status = response[0]
            raw = response[1:]
            if status == INVALID_VARIABLE:
                raise AssertionError("Invalid variable: %s" % key)

        return status

    async def parse_event(self, event_packet):
        event_type = event_packet[0]
        end = len(event_packet) - 3
        raw = event_packet[1:end]
        data = None

        if event_type == TOUCH:  # Touch event
            data = struct.unpack("BBB", raw)
        elif event_type == TOUCH_COORDINATE:  # Touch coordinate
            data = struct.unpack("HHB", raw)
        elif event_type == TOUCH_IN_SLEEP:  # Touch event in sleep mode
            data = struct.unpack("HHB", raw)
        elif event_type == AUTO_SLEEP:  # Device automatically enters into sleep mode
            data = None
        elif event_type == AUTO_WAKE:  # Device automatically wake up
            data = None
        elif event_type == STARTUP:  # System successful start up
            data = None
        elif event_type == SD_CARD_UPGRADE:  # Start SD card upgrade
            data = None
        else:
            print("Other event: 0x%02x", event_type)

        return event_type, data
