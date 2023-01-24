# This file is executed on every boot (including wake-boot from deepsleep)
import esp
import machine


esp.osdebug(0)
#esp.osdebug(None)

#import webrepl
#webrepl.start()

# Set frequency to 240MHz
machine.freq(240000000)
