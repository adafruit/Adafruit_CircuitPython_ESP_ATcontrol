import os
import time
from digitalio import DigitalInOut, Direction, Pull

class espatcommands:

    MODE_STATION = 1
    MODE_SOFTAP = 2
    MODE_SOFTAPSTATION = 3

    def __init__(self, uart, baudrate, *, reset_pin=None, debug=False):
        self._uart = uart
        self._reset_pin = reset_pin
        if self._reset_pin:
            self._reset_pin.direction = Direction.OUTPUT
            self._reset_pin.value = True
        self._debug = debug
        self._versionstrings = []

    @property
    def mode(self):
        reply = self.at_response("AT+CWMODE_CUR?", timeout=0.5).strip(b'\r\n')
        if not reply.startswith(b'+CWMODE_CUR:'):
            raise RuntimeError("Bad response")
        return int(reply[12:])

    @mode.setter
    def mode(self, mode):
        if not mode in (1, 2, 3):
            raise RuntimeError("Invalid Mode")
        self.at_response("AT+CWMODE_CUR=%d" % mode, timeout=3)

    def get_version(self):
        reply = self.at_response("AT+GMR", timeout=0.1).strip(b'\r\n')
        for s in reply.split(b'\r\n'):
            if s:
                self._versionstrings.append(str(s,'utf-8'))
        # get the actual version out
        vers = self._versionstrings[0].split('(')[0]
        if not vers.startswith('AT version:'):
            return False
        self._versionstring = vers[11:]
        return self._versionstring

    @property
    def local_ip(self):
        reply = self.at_response("AT+CIFSR").strip(b'\r\n')
        for s in reply.split(b'\r\n'):
            if s and s.startswith(b'+CIFSR:STAIP,"'):
                return str(s[14:-1],'utf-8')
        raise RuntimeError("Couldn't find IP address")

    def join_AP(self, ssid, password):
        reply = self.at_response('AT+CWJAP="'+ssid+'","'+password+'"', timeout=10)
        if not "WIFI CONNECTED" in reply:
            raise RuntimeError("Couldn't connect to WiFi")
        if not "WIFI GOT IP" in reply:
            raise RuntimeError("Didn't get IP address")

    def scan_APs(self, retries=3):
        for _ in range(retries):
            try:
                scan = self.at_response("AT+CWLAP", timeout=3).split(b'\r\n')
            except RuntimeError:
                continue
            APs = []
            for line in scan:
                if line.startswith(b'+CWLAP:('):
                    AP = line[8:-1].split(b',')
                    for i, val in enumerate(AP):
                        AP[i] = str(val,'utf-8')
                        try:
                            AP[i] = int(AP[i])
                        except ValueError:
                            AP[i] = AP[i].strip('\"') # its a string!
                    APs.append(AP)
            return APs

    def at_response(self, at_cmd, timeout=5, retries=3):
        for _ in range(retries):
            time.sleep(1)
            if self._debug:
                print("--->", at_cmd)
            #self._uart.reset_input_buffer()
            self._uart.write(bytes(at_cmd,'utf-8'))
            self._uart.write(b'\x0d\x0a')
            #uart.timeout = timeout
            #print(uart.readline())  # read echo and toss
            t = time.monotonic()
            response = b''
            while (time.monotonic() - t) < timeout:
                response += self._uart.read(self._uart.in_waiting)
                if response[-4:] == b'OK\r\n':
                    break
            # eat beginning \n and \r
            if self._debug:
                print("<---", response)
            if response[-4:] != b'OK\r\n':
                continue
            return response[:-4]
        raise RuntimeError("Not OK")

    def echo(self, e):
        if e:
            self.at_response("ATE1", timeout=0.5)
        else:
            self.at_response("ATE0", timeout=0.5)


    def soft_reset(self):
        try:
            self._uart.reset_input_buffer()
            reply = self.at_response("AT+RST", timeout=0.5)
            if reply.strip(b'\r\n') == b'AT+RST':
                time.sleep(2)
                self._uart.reset_input_buffer()
                return True
        except:
            pass # fail, see below
        return False

    def hard_reset(self):
        if self._reset_pin:
            self._reset_pin.direction = Direction.OUTPUT
            self._reset_pin.value = False
            time.sleep(0.1)
            self._reset_pin.value = True
            time.sleep(1)
            self._uart.reset_input_buffer()
