import time
import board
import busio
from digitalio import DigitalInOut
from adafruit_espatcontrol import adafruit_espatcontrol

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
esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, run_baudrate=9600,
                                          reset_pin=resetpin, debug=False)
print("Resetting ESP module")
esp.hard_reset()

while True:
    try:
        print("Checking connection...")
        while not esp.is_connected:
            print("Initializing ESP module")
            #print("Scanning for AP's")
            #for ap in esp.scan_APs():
            #    print(ap)
            # settings dictionary must contain 'ssid' and 'password' at a minimum
            print("Connecting...")
            esp.connect(settings)
            print("Connected to AT software version ", esp.version)
        print("Pinging 8.8.8.8...", end="")
        print(esp.ping("8.8.8.8"))
        time.sleep(10)
    except (ValueError,RuntimeError, adafruit_espatcontrol.OKError) as e:
        print("Failed to get data, retrying\n", e)
        continue
