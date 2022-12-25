# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()
import machine

# disable UART 1 at boot
uart1 = machine.UART(1, 115200)
uart1.deinit()

# Set frequency to 240MHz
machine.freq(240000000)
