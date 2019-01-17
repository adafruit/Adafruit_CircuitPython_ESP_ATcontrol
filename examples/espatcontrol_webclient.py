import time
import board
import busio
from digitalio import DigitalInOut
import adafruit_espatcontrol
import adafruit_espatcontrol_requests as requests

# Get wifi details and more from a settings.py file
try:
    from settings import settings
except ImportError:
    print("WiFi settings are kept in settings.py, please add them there!")
    raise

uart = busio.UART(board.TX, board.RX, timeout=0.1)
resetpin = DigitalInOut(board.D5)

URL = "http://wifitest.adafruit.com/testwifi/index.html"
print("ESP AT GET URL", URL)

esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, run_baudrate=9600,
                                          reset_pin=resetpin, debug=False)
print("Resetting ESP module")
esp.hard_reset()

requests.set_interface(esp)

while True:
    try:
        print("Checking connection...")
        while not esp.is_connected:
            print("Connecting...")
            esp.connect(settings)
        # great, lets get the data
        print("Retrieving URL...", end='')
        r = requests.get(URL)
        print("Status:", r.status_code)
        print("Content type:", r.headers['content-type'])
        print("Content size:", r.headers['content-length'])
        print("Encoding:", r.encoding)
        print("Text:", r.text)

        time.sleep(60)
    except (RuntimeError, adafruit_espatcontrol.OKError) as e:
        print("Failed to get data, retrying\n", e)
        continue
