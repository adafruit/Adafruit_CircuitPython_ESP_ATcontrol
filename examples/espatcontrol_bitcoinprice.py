import time
import board
import busio
from digitalio import DigitalInOut
import adafruit_espatcontrol
import ujson
from adafruit_ht16k33 import segments


MY_SSID = "ssidname"
MY_PASS = "thepassword"

URL = "http://api.coindesk.com/v1/bpi/currentprice.json"

uart = busio.UART(board.TX, board.RX, baudrate=115200, timeout=0.1)
resetpin = DigitalInOut(board.D5)

# Create the I2C interface.
i2c = busio.I2C(board.SCL, board.SDA)
# Attach a 7 segment display and display -'s so we know its not live yet
display = segments.Seg7x4(i2c)
display.print('----')

print("Get bitcoin price online")

esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, reset_pin=resetpin, debug=True)
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

    time.sleep(60)
