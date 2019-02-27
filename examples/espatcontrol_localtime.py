import time
import board
import busio
from digitalio import DigitalInOut
import rtc

# ESP32 SPI
from adafruit_espatcontrol import adafruit_espatcontrol, adafruit_espatcontrol_wifimanager

#Use below for Most Boards
import neopixel
status_light = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2) # Uncomment for Most Boards
#Uncomment below for ItsyBitsy M4
#import adafruit_dotstar as dotstar
#status_light = dotstar.DotStar(board.APA102_SCK, board.APA102_MOSI, 1, brightness=0.2)


# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise



# With a Metro or Feather M4
uart = busio.UART(board.TX, board.RX, timeout=0.1)
resetpin = DigitalInOut(board.D5)
rtspin = DigitalInOut(board.D6)

# With a Particle Argon
"""
RX = board.ESP_TX
TX = board.ESP_RX
resetpin = DigitalInOut(board.ESP_WIFI_EN)
rtspin = DigitalInOut(board.ESP_CTS)
uart = busio.UART(TX, RX, timeout=0.1)
esp_boot = DigitalInOut(board.ESP_BOOT_MODE)
from digitalio import Direction
esp_boot.direction = Direction.OUTPUT
esp_boot.value = True
"""


print("ESP AT commands")
esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200,
                                          reset_pin=resetpin, rts_pin=rtspin, debug=False)
wifi = adafruit_espatcontrol_wifimanager.ESPAT_WiFiManager(esp, secrets, status_light)



print("ESP32 local time")

TIME_API = "http://worldtimeapi.org/api/ip"


the_rtc = rtc.RTC()

response = None
while True:
    try:
        print("Fetching json from", TIME_API)
        response = wifi.get(TIME_API)
        break
    except (ValueError, RuntimeError,  adafruit_espatcontrol.OKError) as e:
        print("Failed to get data, retrying\n", e)
        continue

json = response.json()
current_time = json['datetime']
the_date, the_time = current_time.split('T')
year, month, mday = [int(x) for x in the_date.split('-')]
the_time = the_time.split('.')[0]
hours, minutes, seconds = [int(x) for x in the_time.split(':')]

# We can also fill in these extra nice things
year_day = json['day_of_year']
week_day = json['day_of_week']
is_dst = json['dst']

now = time.struct_time((year, month, mday, hours, minutes, seconds, week_day, year_day, is_dst))
print(now)
the_rtc.datetime = now

while True:
    print(time.localtime())
    time.sleep(1)
