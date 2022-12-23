import machine


class I2CMultiplex:

    channel_bits = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]

    address = 0x70
    i2c = None
    
    def __init__(self, i2c, address):
        if isinstance(i2c, machine.I2C):
            self.i2c = i2c
        elif i2c is None:
            raise Exception("i2c parameter is required")
        else:
            raise Exception("i2c is not an I2C object")
        if address is not None:
            self.address = address
        else:
            raise Exception("address parameter is required")

    def activate_channel(self, channel):
        if channel > 7:
            raise Exception("Channel must be between 0 and 7")
        self.i2c.writeto(self.address, self.channel_bits[channel].to_bytes(1, 'little'))

    def activate_channels(self, channel: list):
        channel_mask = 0x00
        for i in channel:
            if i > 7:
                raise Exception("Channel must be between 0 and 7")
            else:
                channel_mask |= self.channel_bits[i]
        self.i2c.writeto(self.address, channel_mask.to_bytes(1, 'little'))
