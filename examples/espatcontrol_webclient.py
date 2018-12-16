import time
import board
import busio
from digitalio import DigitalInOut
import adafruit_espatcontrol

MY_SSID = "my ssid"
MY_PASS = "password"

URL = "http://wifitest.adafruit.com/testwifi/index.html"

uart = busio.UART(board.TX, board.RX, baudrate=115200, timeout=0.1)
resetpin = DigitalInOut(board.D5)

print("Get a URL:", URL)

esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, reset_pin=resetpin, debug=False)
print("Connected to AT software version", esp.get_version())

while True:
    try:
        # Connect to WiFi if not already
        print("Connected to", esp.remote_AP)
        if esp.remote_AP[0] != MY_SSID:
            esp.join_AP(MY_SSID, MY_PASS)
            print("My IP Address:", esp.local_ip)
        # great, lets get the data
        print("Retrieving URL...", end='')
        header, body = esp.request_url(URL)
        print("OK")
    except RuntimeError as e:
        print("Failed to connect, retrying")
        print(e)
        continue

    print('-'*40)
    print(str(body, 'utf-8'))
    print('-'*40)

    time.sleep(60)
