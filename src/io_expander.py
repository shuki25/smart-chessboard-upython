"""
Class for the IO expander
"""

import machine

INPUT_PORT_0_REG = 0x00
INPUT_PORT_1_REG = 0x01
OUTPUT_PORT_0_REG = 0x02
OUTPUT_PORT_1_REG = 0x03
POLARITY_INVERSION_PORT_0_REG = 0x04
POLARITY_INVERSION_PORT_1_REG = 0x05
CONFIGURATION_PORT_0_REG = 0x06
CONFIGURATION_PORT_1_REG = 0x07


class IOExpander:
    def __init__(self, i2c, address):
        if isinstance(i2c, machine.I2C):
            self.i2c = i2c
        elif i2c is None:
            raise Exception("uart parameter is required")
        else:
            raise Exception("uart is not an I2C object")
        self.i2c = i2c
        self.address = address
        self.i2c.writeto_mem(self.address, CONFIGURATION_PORT_0_REG, bytearray([0xFF]))
        self.i2c.writeto_mem(self.address, CONFIGURATION_PORT_1_REG, bytearray([0xFF]))

    def read_input_port(self):
        data = self.i2c.readfrom_mem(self.address, INPUT_PORT_0_REG, 2)
        return data[0] | (data[1] << 8)

    def read_input_port_0(self):
        data = self.i2c.readfrom_mem(self.address, INPUT_PORT_0_REG, 1)
        return data[0]

    def read_input_port_1(self):
        data = self.i2c.readfrom_mem(self.address, INPUT_PORT_1_REG, 1)
        return data[0]

    def write_output_port_0(self, value):
        self.i2c.writeto_mem(self.address, OUTPUT_PORT_0_REG, bytearray([value]))

    def write_output_port_1(self, value):
        self.i2c.writeto_mem(self.address, OUTPUT_PORT_1_REG, bytearray([value]))

    def polarity_inversion_port_0(self, value):
        self.i2c.writeto_mem(
            self.address, POLARITY_INVERSION_PORT_0_REG, bytearray([value])
        )

    def polarity_inversion_port_1(self, value):
        self.i2c.writeto_mem(
            self.address, POLARITY_INVERSION_PORT_1_REG, bytearray([value])
        )

    def configuration_port_0(self, value):
        self.i2c.writeto_mem(self.address, CONFIGURATION_PORT_0_REG, bytearray([value]))

    def configuration_port_1(self, value):
        self.i2c.writeto_mem(self.address, CONFIGURATION_PORT_1_REG, bytearray([value]))
