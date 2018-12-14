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
print("Connected to AT software version", esp.get_version())

while True:
    try:
        display.print('----')
        # Connect to WiFi if not already
        print("Connected to", esp.remote_AP)
        if esp.remote_AP[0] != MY_SSID:
            esp.join_AP(MY_SSID, MY_PASS)
            print("My IP Address:", esp.local_ip)
        # great, lets get the JSON data
        print("Retrieving price...", end='')
        header, body = esp.request_url(URL)
        print("OK")
    except RuntimeError as e:
        print("Failed to connect, retrying")
        print(e)
        continue

    try:
        print("Parsing JSON response...", end='')
        json = ujson.loads(body)
        bitcoin = json["bpi"]["USD"]["rate_float"]
        print("USD per bitcoin:", bitcoin)
        display.print(int(bitcoin))
    except ValueError:
        print("Failed to parse json, retrying")
        continue

    gc.collect()
    print("Free memory:", gc.mem_free() / 1024)
    time.sleep(60)
