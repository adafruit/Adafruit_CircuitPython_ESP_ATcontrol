"""
This example will access an API, grab a number like hackaday skulls, github
stars, price of bitcoin, twitter followers... if you can find something that
spits out JSON data, we can display it!
"""

import gc
import time
import board
import busio
from digitalio import DigitalInOut
from adafruit_espatcontrol import adafruit_espatcontrol
from adafruit_espatcontrol import adafruit_espatcontrol_requests as requests
import ujson
from adafruit_epd.epd import Adafruit_EPD
from adafruit_epd.il0373 import Adafruit_IL0373


# Get wifi details and more from a settings.py file
try:
    from settings import settings
except ImportError:
    print("WiFi settings are kept in settings.py, please add them there!")
    raise

#              CONFIGURATION
TIME_BETWEEN_QUERY = 0  # in seconds
DATA_SOURCE = "https://www.adafruit.com/api/quotes.php"


# create the spi device and pins we will need
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
epd_cs = DigitalInOut(board.D10)
epd_dc = DigitalInOut(board.D11)
epd_rst = DigitalInOut(board.D12)
# give them all to our driver
display = Adafruit_IL0373(104, 212, spi,
                          cs_pin=epd_cs, dc_pin=epd_dc, sramcs_pin=None,
                          rst_pin=epd_rst, busy_pin=None)
display.rotation = 3

uart = busio.UART(board.TX, board.RX, timeout=0.1)
resetpin = DigitalInOut(board.D5)
rtspin = DigitalInOut(board.D6)

# Create the connection to the co-processor and reset
esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, run_baudrate=115200,
                                          reset_pin=resetpin,
                                          rts_pin=rtspin, debug=True)
esp.hard_reset()

requests.set_interface(esp)

# Extract a value from a json string
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

# return a list of lines with wordwrapping
def wrap_nicely(string, max_chars):
    words = string.split(' ')
    the_lines = []
    the_line = ""
    for w in words:
        if len(the_line+' '+w) <= max_chars:
            the_line += ' '+w
        else:
            the_lines.append(line)
            the_line = ''+w
    if the_line:      # last line remaining
        the_lines.append(line)
    return the_lines

def read_le(s):
    # as of this writting, int.from_bytes does not have LE support, DIY!
    result = 0
    shift = 0
    for byte in bytearray(s):
        result += byte << shift
        shift += 8
    return result

class BMPError(Exception):
    pass

def draw_bmp(filename, x, y): # pylint: disable=too-many-locals, too-many-branches
    try:
        with open("/" + filename, "rb") as f:
            print("File opened")
            if f.read(2) != b'BM':  # check signature
                raise BMPError("Not BitMap file")

            bmpFileSize = read_le(f.read(4))
            f.read(4)  # Read & ignore creator bytes

            bmpImageoffset = read_le(f.read(4))  # Start of image data
            headerSize = read_le(f.read(4))
            bmpWidth = read_le(f.read(4))
            bmpHeight = read_le(f.read(4))
            flip = True

            print("Size: %d\nImage offset: %d\nHeader size: %d" %
                  (bmpFileSize, bmpImageoffset, headerSize))
            print("Width: %d\nHeight: %d" % (bmpWidth, bmpHeight))

            if read_le(f.read(2)) != 1:
                raise BMPError("Not singleplane")
            bmpDepth = read_le(f.read(2))  # bits per pixel
            print("Bit depth: %d" % (bmpDepth))
            if bmpDepth != 24:
                raise BMPError("Not 24-bit")
            if read_le(f.read(2)) != 0:
                raise BMPError("Compressed file")

            print("Image OK! Drawing...")

            rowSize = (bmpWidth * 3 + 3) & ~3  # 32-bit line boundary

            for row in range(bmpHeight):  # For each scanline...
                if flip:  # Bitmap is stored bottom-to-top order (normal BMP)
                    pos = bmpImageoffset + (bmpHeight - 1 - row) * rowSize
                else:  # Bitmap is stored top-to-bottom
                    pos = bmpImageoffset + row * rowSize

                # print ("seek to %d" % pos)
                f.seek(pos)
                for col in range(bmpWidth):
                    b, g, r = bytearray(f.read(3))  # BMP files store RGB in BGR
                    color = None
                    if r < 0x80 and g < 0x80 and b < 0x80:
                        color = Adafruit_EPD.BLACK
                    elif r >= 0x80 and g >= 0x80 and b >= 0x80:
                        color = Adafruit_EPD.WHITE
                    elif r >= 0x80:
                        color = Adafruit_EPD.RED
                    display.pixel(x+row, y+col, color)

    except OSError as e:
        if e.args[0] == 28:
            raise OSError("OS Error 28 0.25")
        else:
            raise OSError("OS Error 0.5")
    except BMPError as e:
        print("Failed to parse BMP: " + e.args[0])

quote = "Eternal vigilance is not only the price of liberty; eternal vigilance is the price of human decency"  # pylint: disable=line-too-long
author = "Aldous Huxley"
lines = wrap_nicely(str(quote, 'utf-8'), (210 - 50)//6)
print(lines)
start_x = 10
start_y = 10
display.fill(Adafruit_EPD.WHITE)
draw_bmp("lilblinka.bmp", display.width - 75, display.height - 80)
for i,line in enumerate(lines):
    display.text(line, start_x, start_y+i*10, Adafruit_EPD.BLACK)
display.text(author, 10, 100-20, Adafruit_EPD.RED)

display.display()


while True:
    try:
        while not esp.is_connected:
            # settings dictionary must contain 'ssid' and 'password' at a minimum
            esp.connect(settings)
        # great, lets get the data

        print("Retrieving data source...", end='')
        req = requests.get(DATA_SOURCE)
        print("Reply is OK!")
    except (ValueError, RuntimeError, adafruit_espatcontrol.OKError) as e:
        print("Failed to get data, retrying\n", e)
        continue

    body = req.text
    print('-'*40, "Size: ", len(body))
    print(str(body, 'utf-8'))
    print('-'*40)
    quote = get_value(body, [0, "text"])
    author = get_value(body, [0, "author"])
    if not quote or not author:
        continue
    print(quote, author)

    lines = wrap_nicely(str(quote, 'utf-8'), (display.width - 50)//6)
    start_x = 10
    start_y = 10
    display.fill(Adafruit_EPD.WHITE)
    draw_bmp("lilblinka.bmp", display.width - 75, display.height - 80)
    for i, line in enumerate(lines):
        display.text(line, start_x, start_y+i*10, Adafruit_EPD.BLACK)
    display.text(author, 10, display.height-20, Adafruit_EPD.RED)
    display.display()

    # normally we wouldn't have to do this, but we get bad fragments
    req = None
    gc.collect()
    print(gc.mem_free())  # pylint: disable=no-member
    time.sleep(TIME_BETWEEN_QUERY)
