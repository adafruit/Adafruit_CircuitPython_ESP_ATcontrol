import time
import board
import busio
from digitalio import DigitalInOut
import adafruit_espatcontrol

# Get wifi details and more from a settings.py file
try:
    from settings import settings
except ImportError:
    print("WiFi settings are kept in settings.py, please add them there!")
    raise

# With a Metro or Feather M4
uart = busio.UART(board.TX, board.RX, timeout=0.1)
resetpin = DigitalInOut(board.D5)

# With a Particle Argon
"""
uart = busio.UART(board.ESP_RX, board.ESP_TX, timeout=0.1)
resetpin = DigitalInOut(board.ESP_WIFI_EN)
esp_boot = DigitalInOut(board.ESP_BOOT_MODE)
from digitalio import Direction
esp_boot.direction = Direction.OUTPUT
esp_boot.value = True
"""

URL = "http://wifitest.adafruit.com/testwifi/index.html"
print("ESP AT GET URL", URL)

esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, run_baudrate=9600,
                                          reset_pin=resetpin, debug=False)
print("Resetting ESP module")
esp.hard_reset()

while True:
    try:
        print("Checking connection...")
        while not esp.is_connected:
            print("Connecting...")
            esp.connect(settings)
        # great, lets get the data
        print("Retrieving URL...", end='')
        header, body = esp.request_url(URL)
        print("OK")

        print('-'*40)
        print(str(body, 'utf-8'))
        print('-'*40)

        time.sleep(60)
    except (RuntimeError, adafruit_espatcontrol.OKError) as e:
        print("Failed to get data, retrying\n", e)
        continue
