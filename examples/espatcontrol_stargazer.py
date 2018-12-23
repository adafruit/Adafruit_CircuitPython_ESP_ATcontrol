import time
import board
import busio
from digitalio import DigitalInOut
import adafruit_espatcontrol
import ujson
import gc

MY_SSID = "netgear"
MY_PASS = "hunter2"

# Some URLs to try!
URL = "https://api.github.com/repos/adafruit/circuitpython"   # github stars

uart = busio.UART(board.TX, board.RX, baudrate=115200, timeout=0.1)
resetpin = DigitalInOut(board.D5)
# we really need flow control for this example to work
rtspin = DigitalInOut(board.D9)

print("Get a URL:", URL)

esp = adafruit_espatcontrol.ESP_ATcontrol(uart, 115200, reset_pin=resetpin,
                                          rts_pin=rtspin, debug=True)
print("Connected to AT software version", esp.get_version())

def connect_to_wifi(ssid, password):
    # Connect to WiFi if not already
    while True:
        try:
            AP = esp.remote_AP
            print("Connected to", AP)
            if AP[0] != ssid:
                esp.join_AP(ssid, password)
                print("My IP Address:", esp.local_ip)
            return  # yay!
        except RuntimeError as e:
            print("Failed to connect, retrying\n", e)
            continue
        except adafruit_espatcontrol.OKError as e:
            print("Failed to connect, retrying\n", e)
            continue


def get_stars(response):
    try:
        print("Parsing JSON response...", end='')
        json = ujson.loads(body)
        return json["stargazers_count"]
    except ValueError:
        print("Failed to parse json, retrying")
        return None

# we'll save the stargazer #
stars = None

while True:
    connect_to_wifi(MY_SSID, MY_PASS)
    # great, lets get the data
    try:
        print("Retrieving URL...", end='')
        header, body = esp.request_url(URL)
        print("Reply is OK!")
    except:
        continue  # we'll retry
    #print('-'*40, "Size: ", len(body))
    #print(str(body, 'utf-8'))
    #print('-'*40)
    stars = get_stars(body)
    print("stargazers:", stars)
    # normally we wouldn't have to do this, but we get bad fragments
    header = body = None
    gc.collect()
    print(gc.mem_free())
    # OK hang out and wait to do it again
    time.sleep(10)
