"""
This example will query ThingSpeak channel 1417 "CheerLights" and display the
color on a NeoPixel ring or strip
"""
import gc
import time
import board
import busio
from digitalio import DigitalInOut
import adafruit_espatcontrol
import neopixel
import ujson
import adafruit_fancyled.adafruit_fancyled as fancy



# Get wifi details and more from a settings.py file
try:
    from settings import settings
except ImportError:
    print("WiFi settings are kept in settings.py, please add them there!")
    raise

#              CONFIGURATION
TIME_BETWEEN_QUERY = 10  # in seconds

# Cheerlights!
DATA_SOURCE = "http://api.thingspeak.com/channels/1417/feeds.json?results=1"
DATA_LOCATION = ["feeds", 0, "field2"]

uart = busio.UART(board.TX, board.RX, timeout=0.1)
resetpin = DigitalInOut(board.D5)
rtspin = DigitalInOut(board.D9)

# Create the connection to the co-processor and reset
esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, run_baudrate=460800,
                                          reset_pin=resetpin,
                                          rts_pin=rtspin, debug=True)
esp.hard_reset()

# neopixels
pixels = neopixel.NeoPixel(board.A1, 16, brightness=0.3)
pixels.fill(0)
builtin = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.1)
builtin[0] = 0

# we'll save the value in question
last_value = value = None
the_time = None
times = 0

def get_value(response, location):
    """Extract a value from a json object, based on the path in 'location'"""
    try:
        print("Parsing JSON response...", end='')
        json = ujson.loads(response)
        print("parsed OK!")
        for x in location:
            json = json[x]
        return json
    except ValueError:
        print("Failed to parse json, retrying")
        return None

while True:
    try:
        while not esp.is_connected:
            builtin[0] = (100, 0, 0)
            # settings dictionary must contain 'ssid' and 'password' at a minimum
            esp.connect(settings)
        builtin[0] = (0, 100, 0)
        # great, lets get the data
        print("Retrieving data source...", end='')
        builtin[0] = (100, 100, 0)
        header, body = esp.request_url(DATA_SOURCE)
        builtin[0] = (0, 0, 100)
        print("Reply is OK!")
    except (RuntimeError, adafruit_espatcontrol.OKError) as e:
        print("Failed to get data, retrying\n", e)
        continue
    print('-'*40, "Size: ", len(body))
    print(str(body, 'utf-8'))
    print('-'*40)
    # For mystery reasons, there's two numbers before and after the json data
    lines = body.split(b'\r\n')  # so split into lines
    try:
        value = get_value(lines[1], DATA_LOCATION) # an get the middle chunk
        builtin[0] = (100, 100, 100)
        if not value:
            continue
        print(times, the_time, "value:", value)
    except IndexError as e:
        print("IndexError processing Body, retrying\n", e)
        continue
    if last_value != value:
        color = int(value[1:],16)
        red = color >> 16 & 0xFF
        green = color >> 8 & 0xFF
        blue = color& 0xFF
        gamma_corrected = fancy.gamma_adjust(fancy.CRGB(red, green, blue)).pack()

        pixels.fill(gamma_corrected)
        last_value = value
    times += 1

    # normally we wouldn't have to do this, but we get bad fragments
    header = body = None
    gc.collect()
    print(gc.mem_free())  # pylint: disable=no-member
    time.sleep(TIME_BETWEEN_QUERY)
