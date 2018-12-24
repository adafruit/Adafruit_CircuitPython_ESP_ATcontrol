import board
import busio
import time
from digitalio import DigitalInOut
import adafruit_espatcontrol
import ujson
from adafruit_ht16k33 import segments

# Get wifi details and more from a settings.py file
try:
    from settings import settings
except ImportError:
    print("WiFi settings are kept in settings.py, please add them there!")
    raise

# UART interface + reset pin for the module
uart = busio.UART(board.TX, board.RX, timeout=0.1)
resetpin = DigitalInOut(board.D5)

# Create the I2C interface.
i2c = busio.I2C(board.SCL, board.SDA)
# Attach a 7 segment display and display -'s so we know its not live yet
display = segments.Seg7x4(i2c)
display.print('----')

URL = "http://api.coindesk.com/v1/bpi/currentprice.json"
print("ESP bitcoin price online from", URL)

esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, run_baudrate=9600,
                                          reset_pin=resetpin, debug=False)
print("Resetting ESP module")
esp.hard_reset()

while True:
    try:
        display.print('----')
        print("Checking connection...")
        while not esp.is_connected:
            print("Connecting...")
            esp.connect(settings)
        # great, lets get the data
        print("Retrieving URL...", end='')
        header, body = esp.request_url(URL)
        print("OK")

        print("Parsing JSON response...", end='')
        json = ujson.loads(body)
        bitcoin = json["bpi"]["USD"]["rate_float"]
        print("USD per bitcoin:", bitcoin)
        display.print(int(bitcoin))

        time.sleep(60)

    except (RuntimeError, adafruit_espatcontrol.OKError) as e:
        print("Failed to get data, retrying\n", e)
        continue
    except ValueError:
        print("Failed to parse json, retrying")
        continue
