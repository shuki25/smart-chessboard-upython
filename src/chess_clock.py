from ssd1306 import SSD1306_I2C
from i2c_multiplex import I2CMultiplex
import lcdfont20
from writer import Writer
import time
import math

# Constants
OLED_WIDTH = 128
OLED_HEIGHT = 32


class ChessClock:
    oled: SSD1306_I2C
    fw: Writer
    mux_port: list
    i2c_mux: I2CMultiplex
    clock_countdown: int
    clock_running = False
    last_time = time.ticks_ms()  # time is tracked in milliseconds since start up
    prev_clock_text = "  00 :00"

    def __init__(self, i2c, i2c_mux: I2CMultiplex, mux_port: list):
        """
        :param i2c: I2C object
        :param i2c_mux: I2CMultiplex object
        :param mux_port: list of ports to activate on the multiplexer
        """
        self.mux_port = mux_port
        self.i2c_mux = i2c_mux
        self.i2c_mux.activate_channels(mux_port)
        self.oled = SSD1306_I2C(128, 32, i2c)
        self.fw = Writer(self.oled, lcdfont20)
        self.oled.fill(0)
        self.oled.text("Ready.", 0, 0)
        self.show()

    def show(self):
        self.i2c_mux.activate_channels(self.mux_port)
        self.oled.show()

    def display_time(self, text, x=0, y=0, clear=True, align="L"):
        if clear:
            self.clear()
        if align == "R":
            x = self.right_align(text, x)
        elif align == "C":
            x = self.center_align(text, x)
        Writer.set_textpos(self.oled, y, x)
        self.fw.printstring(str(text))
        self.show()

    def display_text(self, text, x=0, y=0, clear=True, align="L"):
        if clear:
            self.clear()
        if align == "R":
            x = self.right_align(text, x, font_width=10)
        elif align == "C":
            x = self.center_align(text, x, font_width=10)
        self.oled.text(text, x, y)
        self.show()

    def clear(self):
        self.oled.fill(0)
        self.show()

    def set_clock(self, seconds):
        self.clock_countdown = seconds
        self.clock_running = False
        mins, secs = divmod(seconds, 60)
        clock_text = "   {:02.0f} :{:02.0f}".format(mins, secs)
        print("Setting clock to %s" % clock_text)
        self.display_time(clock_text, 0, 12, align="R")

    def start_clock(self):
        self.clock_running = True
        self.last_time = time.ticks_ms()
        self.update_clock()

    def stop_clock(self):
        if self.clock_running:
            now = time.ticks_ms()
            elapsed = (now - self.last_time) / 1000
            self.last_time = now
            self.clock_countdown -= elapsed
        self.clock_running = False
        self.update_clock()

    def update_clock(self):
        if self.clock_running:
            now = time.ticks_ms()
            elapsed = (now - self.last_time) / 1000
            self.last_time = now
            self.clock_countdown -= elapsed
        if self.clock_countdown < 0:
            self.clock_countdown = 0
            self.clock_running = False
        else:
            mins, secs = divmod(math.floor(self.clock_countdown), 60)
            if mins < 1:
                clock_text = "     {:04.1f}".format(secs)
            else:
                clock_text = "   {:02.0f} :{:02.0f}".format(mins, secs)
            if self.prev_clock_text != clock_text:
                self.display_time(clock_text, 0, 12, align="R", clear=False)
            self.prev_clock_text = clock_text

    def is_clock_running(self):
        return self.clock_running

    def get_clock_countdown(self):
        return self.clock_countdown

    def update_clock_countdown(self, seconds):
        self.clock_countdown = seconds

    def add_clock_countdown(self, seconds):
        self.clock_countdown += seconds

    def right_align(self, text, x_offset=0, font_width=lcdfont20.max_width()):
        return OLED_WIDTH - (len(text) * font_width) - x_offset

    def center_align(self, text, x_offset=0, font_width=lcdfont20.max_width()):
        return (OLED_WIDTH - (len(text) * font_width)) // 2 - x_offset
