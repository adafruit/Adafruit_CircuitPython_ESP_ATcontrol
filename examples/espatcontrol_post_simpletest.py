import time
import board
import busio
from digitalio import DigitalInOut
import adafruit_espatcontrol

MY_SSID = "yourssid"
MY_PASS = "yourpassword"

URL = "http://io.adafruit.com/api/v2/webhooks/feed/<YOURWEBHOOK>?value="

RX = board.ESP_TX
TX = board.ESP_RX
resetpin = DigitalInOut(board.ESP_WIFI_EN)


uart = busio.UART(TX, RX, baudrate=115200, timeout=0.1)
#uart.baudrate=9600
print("Get a URL:", URL)

esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, reset_pin=resetpin, debug=True)
print("Connected to AT software version", esp.get_version())
counter = 0 
while True:
    try:
        # Connect to WiFi if not already
        print("Connected to", esp.remote_AP)
        if esp.remote_AP[0] != MY_SSID:
            esp.join_AP(MY_SSID, MY_PASS)
            print("My IP Address:", esp.local_ip)
        # great, lets get the data
        print("Retrieving URL...", end='')
        header, body = esp.post_url(URL+str(counter))
        counter = counter + 1
        print("OK")
    except RuntimeError as e:
        print("Failed to connect, retrying")
        print(e)
        continue

    print('-'*40)
    print(str(body, 'utf-8'))
    print('-'*40)

    time.sleep(60)
