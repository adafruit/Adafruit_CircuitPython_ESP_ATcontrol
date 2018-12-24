import time
import board
import busio
import audioio
from digitalio import DigitalInOut
from Adafruit_CircuitPython_ESP_ATcontrol import adafruit_espatcontrol
from adafruit_ht16k33 import segments
import neopixel
import ujson
import gc

uart = busio.UART(board.TX, board.RX, timeout=0.1)
resetpin = DigitalInOut(board.D5)
rtspin = DigitalInOut(board.D9)

# Get wifi details and more from a settings.py file
try:
    from settings import settings
except ImportError:
    print("WiFi settings are kept in settings.py, please add them there!")
    raise

# Some URLs to try!
URL = "https://api.github.com/repos/adafruit/circuitpython"   # github stars
if 'github_token' in settings:
    URL += "?access_token="+settings['github_token']

# Create the connection to the co-processor and reset
esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, run_baudrate=921600, 
                                          reset_pin=resetpin,
                                          rts_pin=rtspin, debug=True)
esp.hard_reset()

# Create the I2C interface.
i2c = busio.I2C(board.SCL, board.SDA)
# Attach a 7 segment display and display -'s so we know its not live yet
display = segments.Seg7x4(i2c)
display.print('----')

# neopixels
pixels = neopixel.NeoPixel(board.A1, 16, brightness=0.4, pixel_order=(1, 0, 2, 3))
pixels.fill(0)

# music!
wave_file = open("coin.wav", "rb")
wave = audioio.WaveFile(wave_file)

# we'll save the stargazer #
last_stars = stars = None
the_time = None
times = 0

def chime_light():
    with audioio.AudioOut(board.A0) as audio:
        audio.play(wave)
        for i in range(0, 100, 10):
            pixels.fill((i,i,i))
        while audio.playing:
            pass
        for i in range(100, 0, -10):
            pixels.fill((i,i,i))
        pixels.fill(0)

def get_stars(response):
    try:
        print("Parsing JSON response...", end='')
        json = ujson.loads(body)
        print("parsed OK!")
        return json["stargazers_count"]
    except ValueError:
        print("Failed to parse json, retrying")
        return None

while True:
    try:
        while not esp.is_connected:
            # settings dictionary must contain 'ssid' and 'password' at a minimum
            esp.connect(settings)
        # great, lets get the data
        # get the time
        the_time = esp.sntp_time

        print("Retrieving URL...", end='')
        header, body = esp.request_url(URL)
        print("Reply is OK!")
    except (RuntimeError, adafruit_espatcontrol.OKError) as e:
        print("Failed to get data, retrying\n", e)
        continue
    #print('-'*40, "Size: ", len(body))
    #print(str(body, 'utf-8'))
    #print('-'*40)
    stars = get_stars(body)
    if not stars:
        continue
    print(times, the_time, "stargazers:", stars)
    display.print(int(stars))

    if last_stars != stars:
        chime_light() # animate the neopixels
        last_stars = stars
    times += 1
    # normally we wouldn't have to do this, but we get bad fragments
    header = body = None
    gc.collect()
    print(gc.mem_free())
