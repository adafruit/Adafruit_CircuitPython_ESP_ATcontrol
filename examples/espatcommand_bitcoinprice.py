import time
import board
import busio
from digitalio import DigitalInOut, Direction, Pull
import adafruit_espatcommands
import ujson
from adafruit_ht16k33 import segments
import gc


MY_SSID = "my ssid"
MY_PASS = "the password"
#URL = "http://wifitest.adafruit.com/testwifi/index.html"
URL = "http://api.coindesk.com/v1/bpi/currentprice.json"

uart = busio.UART(board.TX, board.RX, baudrate=115200, timeout=0.1)
resetpin = DigitalInOut(board.D5)

# Create the I2C interface.
i2c = busio.I2C(board.SCL, board.SDA)
display = segments.Seg7x4(i2c)
display.print('----')

print("Get bitcoin")
print("Free memory:", gc.mem_free() / 1024)
esp = adafruit_espatcommands.espatcommands(uart, 115200, reset_pin = resetpin, debug=True)
print("Connected to AT software version ", esp.get_version())

time.sleep(3)

esp.join_AP(MY_SSID, MY_PASS)
print("My IP Address:", esp.local_ip)

while True:
    try:
        display.print('----')
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
