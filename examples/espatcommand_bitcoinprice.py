import time
import board
import busio
from digitalio import DigitalInOut, Direction, Pull
from adafruit_espatcommands import adafruit_espatcommands
import ujson
from adafruit_ht16k33 import segments
import gc


MY_SSID = "adafruit"
MY_PASS = "password"
#URL = "http://wifitest.adafruit.com/testwifi/index.html"
URL = "http://api.coindesk.com/v1/bpi/currentprice.json"

uart = busio.UART(board.TX, board.RX, baudrate=115200, timeout=0.1)
resetpin = DigitalInOut(board.D5)

# Create the I2C interface.
i2c = busio.I2C(board.SCL, board.SDA)
display = segments.Seg7x4(i2c)
display.print('----')

print("Get bitcoin price online")
print("Free memory:", gc.mem_free() / 1024)

esp = adafruit_espatcommands.espatcommands(uart, 115200, reset_pin = resetpin, debug=True)
print("Connected to AT software version ", esp.get_version())

while True:
    try:
        display.print('----')
        # Connect to WiFi if not already
        if esp.remote_AP != MY_SSID:
            esp.join_AP(MY_SSID, MY_PASS)
            print("My IP Address:", esp.local_ip)

        # great, lets get the JSON data
        header, body = esp.request_url(URL)
        json = ujson.loads(body)
        bitcoin = json["bpi"]["USD"]["rate_float"]
        print("USD per bitcoin:", bitcoin)
        display.print(int(bitcoin))
        time.sleep(5 * 60)  # 5 minutes
    except RuntimeError:
        print("Failed to connect, retrying")
        continue
print(body)

gc.collect()
print("Free memory:", gc.mem_free() / 1024)
