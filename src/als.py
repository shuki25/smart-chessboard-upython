"""
Ambient Light Sensor class:

This class is used to read the ambient light sensor with LTR-F216A chip. The
chip is connected to ESP32 via I2C bus.

"""

import machine

ALS_ADDRESS = 0x53

ALS_CONTROL = 0x00
ALS_MEAS_RES = 0x04
ALS_GAIN = 0x05
ALS_STATUS = 0x07
ALS_DATA_0 = 0x0D
ALS_DATA_1 = 0x0E
ALS_DATA_2 = 0x0F

ALS_CONTROL_DISABLE = 0x00
ALS_CONTROL_ENABLE_MASK = 0x02
ALS_CONTROL_RESET_MASK = 0x10

ALS_MEAS_RES_16BIT = 0x04
ALS_MEAS_RES_17BIT = 0x03
ALS_MEAS_RES_18BIT = 0x02
ALS_MEAS_RES_19BIT = 0x01
ALS_MEAS_RES_20BIT = 0x00

ALS_MEAS_RES_25MS = 0x04 << 4
ALS_MEAS_RES_50MS = 0x03 << 4
ALS_MEAS_RES_100MS = 0x02 << 4
ALS_MEAS_RES_200MS = 0x01 << 4
ALS_MEAS_RES_400MS = 0x00 << 4
ALS_MEAS_RES_MASK = 0x07 << 4

ALS_MEAS_RATE_25MS = 0x00
ALS_MEAS_RATE_50MS = 0x01
ALS_MEAS_RATE_100MS = 0x02
ALS_MEAS_RATE_500MS = 0x03
ALS_MEAS_RATE_MASK = 0x07

ALS_MEAS_DEFAULT = ALS_MEAS_RES_100MS | ALS_MEAS_RATE_100MS

ALS_GAIN_1X = 0x00
ALS_GAIN_3X = 0x01
ALS_GAIN_6X = 0x02
ALS_GAIN_9X = 0x03
ALS_GAIN_18X = 0x04
ALS_GAIN_MASK = 0x07

ALS_GAIN_FACTOR = [1, 3, 6, 9, 18]
ALS_INTEGRATION_FACTOR = [4, 2, 1, 0.50, 0.25]

ALS_STATUS_DATA_READY_MASK = 0x08
ALS_STATUS_INTERRUPT_MASK = 0x10

ALS_INT_CFG = 0x19
ALS_INT_CFG_ENABLE_MASK = 0x04

ALS_INT_PST = 0x1A
ALS_INT_PST_MASK = 0xF0

ALS_THRES_UP_0 = 0x21
ALS_THRES_UP_1 = 0x22
ALS_THRES_UP_2 = 0x23
ALS_THRES_LOW_0 = 0x24
ALS_THRES_LOW_1 = 0x25
ALS_THRES_LOW_2 = 0x26


class AmbientLightSensor:
    def __init__(self, i2c: machine.I2C, address=ALS_ADDRESS):
        if isinstance(i2c, machine.I2C):
            self.i2c = i2c
        elif i2c is None:
            raise Exception("i2c parameter is required")
        else:
            raise Exception("i2c is not an I2C object")
        self.address = address

        # Set to default settings
        self.i2c.writeto_mem(self.address, ALS_CONTROL, bytearray([ALS_CONTROL_ENABLE_MASK]))
        self.i2c.writeto_mem(self.address, ALS_MEAS_RES, bytearray([ALS_MEAS_DEFAULT]))
        self.i2c.writeto_mem(self.address, ALS_GAIN, bytearray([ALS_GAIN_3X]))

    def read(self):
        data = self.i2c.readfrom_mem(self.address, ALS_DATA_0, 3)
        return data[0] | (data[1] << 8) | (data[2] << 16)

    def read_raw(self):
        data = self.i2c.readfrom_mem(self.address, ALS_DATA_0, 3)
        return data

    def read_raw_0(self):
        data = self.i2c.readfrom_mem(self.address, ALS_DATA_0, 1)
        return data[0]

    def read_raw_1(self):
        data = self.i2c.readfrom_mem(self.address, ALS_DATA_1, 1)
        return data[0]

    def read_raw_2(self):
        data = self.i2c.readfrom_mem(self.address, ALS_DATA_2, 1)
        return data[0]

    def read_status(self):
        data = self.i2c.readfrom_mem(self.address, ALS_STATUS, 1)
        return data[0]

    def read_status_data_ready(self):
        data = self.i2c.readfrom_mem(self.address, ALS_STATUS, 1)
        return True if data[0] & ALS_STATUS_DATA_READY_MASK else False

    def read_status_interrupt(self):
        data = self.i2c.readfrom_mem(self.address, ALS_STATUS, 1)
        return True if data[0] & ALS_STATUS_INTERRUPT_MASK else False

    def read_control(self):
        data = self.i2c.readfrom_mem(self.address, ALS_CONTROL, 1)
        return data[0]

    def is_enabled(self):
        data = self.i2c.readfrom_mem(self.address, ALS_CONTROL, 1)
        return True if data[0] & ALS_CONTROL_ENABLE_MASK else False

    def enable(self):
        self.i2c.writeto_mem(self.address, ALS_CONTROL, bytearray([ALS_CONTROL_ENABLE_MASK]))

    def disable(self):
        self.i2c.writeto_mem(self.address, ALS_CONTROL, bytearray([ALS_CONTROL_DISABLE]))

    def reset(self):
        self.i2c.writeto_mem(self.address, ALS_CONTROL, bytearray([ALS_CONTROL_RESET_MASK]))

    def read_measurement_resolution(self):
        data = self.i2c.readfrom_mem(self.address, ALS_MEAS_RES, 1)
        return data[0] & ALS_MEAS_RES_MASK

    def set_measurement_resolution(self, resolution):
        data = self.i2c.readfrom_mem(self.address, ALS_MEAS_RES, 1)
        val = data[0] & ~ALS_MEAS_RES_MASK
        val |= resolution
        self.i2c.writeto_mem(self.address, ALS_MEAS_RES, bytearray([val]))

    def read_measurement_rate(self):
        data = self.i2c.readfrom_mem(self.address, ALS_MEAS_RES, 1)
        return data[0] & ALS_MEAS_RATE_MASK

    def set_measurement_rate(self, rate):
        data = self.i2c.readfrom_mem(self.address, ALS_MEAS_RES, 1)
        val = data[0] & ~ALS_MEAS_RATE_MASK
        val |= rate
        self.i2c.writeto_mem(self.address, ALS_MEAS_RES, bytearray([val]))

    def read_gain(self):
        data = self.i2c.readfrom_mem(self.address, ALS_GAIN, 1)
        return data[0]

    def set_gain(self, gain):
        gain = gain & ALS_GAIN_MASK
        self.i2c.writeto_mem(self.address, ALS_GAIN, bytearray([gain]))

    def is_interrupt_enabled(self):
        data = self.i2c.readfrom_mem(self.address, ALS_INT_CFG, 1)
        return True if data[0] & ALS_INT_CFG_ENABLE_MASK else False

    def enable_interrupt(self):
        data = self.i2c.readfrom_mem(self.address, ALS_INT_CFG, 1)
        val = data[0] | ALS_INT_CFG_ENABLE_MASK
        self.i2c.writeto_mem(self.address, ALS_INT_CFG, bytearray([val]))

    def disable_interrupt(self):
        data = self.i2c.readfrom_mem(self.address, ALS_INT_CFG, 1)
        val = data[0] & ~ALS_INT_CFG_ENABLE_MASK
        self.i2c.writeto_mem(self.address, ALS_INT_CFG, bytearray([val]))

    def read_interrupt_persistence(self):
        data = self.i2c.readfrom_mem(self.address, ALS_INT_PST, 1)
        return (data[0] & ALS_INT_PST_MASK) >> 4

    def set_interrupt_persistence(self, persistence):
        persistence = persistence & 0x0F
        persistence <<= 4
        data = self.i2c.readfrom_mem(self.address, ALS_INT_PST, 1)
        val = data[0] & ~ALS_INT_PST_MASK
        val |= persistence
        self.i2c.writeto_mem(self.address, ALS_INT_PST, bytearray([val]))

    def read_interrupt_threshold_upper(self):
        data = self.i2c.readfrom_mem(self.address, ALS_THRES_UP_0, 3)
        return data[0] | (data[1] << 8) | (data[2] << 16)

    def read_interrupt_threshold_lower(self):
        data = self.i2c.readfrom_mem(self.address, ALS_THRES_LOW_0, 3)
        return data[0] | (data[1] << 8) | (data[2] << 16)

    def set_interrupt_threshold_upper(self, threshold):
        data = bytearray([threshold & 0xFF, (threshold >> 8) & 0xFF, (threshold >> 16) & 0xFF])
        self.i2c.writeto_mem(self.address, ALS_THRES_UP_0, data)

    def set_interrupt_threshold_lower(self, threshold):
        data = bytearray([threshold & 0xFF, (threshold >> 8) & 0xFF, (threshold >> 16) & 0xFF])
        self.i2c.writeto_mem(self.address, ALS_THRES_LOW_0, data)

    def adjust_interrupt_threshold_range(self, percentage):
        current_value = self.read()
        max_value = 0xFFFFFF
        resolution = self.read_measurement_resolution() >> 4
        if resolution == ALS_MEAS_RES_16BIT:
            max_value = 65535
        elif resolution == ALS_MEAS_RES_17BIT:
            max_value = 131071
        elif resolution == ALS_MEAS_RES_18BIT:
            max_value = 262143
        elif resolution == ALS_MEAS_RES_19BIT:
            max_value = 524287
        elif resolution == ALS_MEAS_RES_20BIT:
            max_value = 1048575
        range_half = int((max_value * percentage / 100) / 2)

        print("Current value: %d" % current_value)
        print("Max value: %d" % max_value)
        print("Range half: %d" % range_half)

        upper = current_value + range_half
        if upper > max_value:
            upper = max_value
        print("Upper: %d" % upper)

        lower = current_value - range_half
        if lower < 0:
            lower = 0
        if upper > 0xFFFFFF:
            upper = 0xFFFFFF
        print("Lower: %d" % lower)

        self.set_interrupt_threshold_upper(upper)
        self.set_interrupt_threshold_lower(lower)

    def lux_calc(self):
        """
        Calculate the lux value

        formula: lux = (0.45 * ALS_DATA) / (ALS_GAIN * (ALS_MEAS_RES / ALS_MEAS_RATE))

        Returns:
            Lux value
        """
        als_data = self.read()
        als_gain = self.read_gain()
        gain = ALS_GAIN_FACTOR[als_gain]
        als_meas_res = self.read_measurement_resolution()
        integration = ALS_INTEGRATION_FACTOR[als_meas_res >> 4]

        lux = (0.45 * als_data) / (gain * integration)

        return lux
