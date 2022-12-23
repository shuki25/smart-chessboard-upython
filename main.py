import uasyncio
import app
import ntptime
import wifimgr


async def connect_wifi():
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

loop = uasyncio.get_event_loop()
# loop.create_task(connect_wifi())
loop.create_task(app.main())
loop.run_forever()
