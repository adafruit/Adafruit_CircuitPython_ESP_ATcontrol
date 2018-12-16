# The MIT License (MIT)
#
# Copyright (c) 2018 ladyada for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`adafruit_espatcontrol`
====================================================

Use the ESP AT command sent to communicate with the Interwebs.
Its slow, but works to get data into CircuitPython

Command set:
https://www.espressif.com/sites/default/files/documentation/4a-esp8266_at_instruction_set_en.pdf

Examples:
https://www.espressif.com/sites/default/files/documentation/4b-esp8266_at_command_examples_en.pdf

* Author(s): ladyada

Implementation Notes
--------------------

**Hardware:**

* Adafruit `ESP8266 Huzzah Breakout
  <https://www.adafruit.com/product/2471>`_ (Product ID: 2471)

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

import time
from digitalio import Direction

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_espATcontrol.git"


class ESP_ATcontrol:
    """A wrapper for AT commands to a connected ESP8266 or ESP32 module to do
    some very basic internetting. The ESP module must be pre-programmed with
    AT command firmware, you can use esptool or our CircuitPython miniesptool
    to upload firmware"""
    MODE_STATION = 1
    MODE_SOFTAP = 2
    MODE_SOFTAPSTATION = 3
    TYPE_TCP = "TCP"
    TYPE_UDP = "UDP"
    TYPE_SSL = "SSL"

    def __init__(self, uart, baudrate, *, reset_pin=None, debug=False):
        self._uart = uart
        self._reset_pin = reset_pin
        if self._reset_pin:
            self._reset_pin.direction = Direction.OUTPUT
            self._reset_pin.value = True
        self._debug = debug
        self._versionstrings = []
        self._version = None
        # Connect and sync
        if not self.sync():
            if not self.soft_reset():
                self.hard_reset()
                self.soft_reset()
        self.baudrate = baudrate
        self.echo(False)


    @property
    def baudrate(self):
        """The baudrate of our UART connection"""
        return self._uart.baudrate

    @baudrate.setter
    def baudrate(self, baudrate):
        """Change the modules baudrate via AT commands and then check
        that we're still sync'd."""
        if self._uart.baudrate != baudrate:
            at_cmd = "AT+UART_CUR="+str(baudrate)+",8,1,0,0\r\n"
            if self._debug:
                print("Changing baudrate to:", baudrate)
                print("--->", at_cmd)
            self._uart.write(bytes(at_cmd, 'utf-8'))
            time.sleep(.25)
            self._uart.baudrate = baudrate
            time.sleep(.25)
            self._uart.reset_input_buffer()
            if not self.sync():
                raise RuntimeError("Failed to resync after Baudrate change")



    def request_url(self, url, ssl=False):
        """Send an HTTP request to the URL. If the URL starts with https://
        we will force SSL and use port 443. Otherwise, you can select whether
        you want ssl by passing in a flag."""
        if url.startswith("https://"):
            ssl = True
            url = url[8:]
        if url.startswith("http://"):
            url = url[7:]
        domain, path = url.split('/', 1)
        path = '/'+path
        port = 80
        if ssl:
            port = 443
        if not self.connect(self.TYPE_TCP, domain, port, keepalive=10, retries=3):
            raise RuntimeError("Failed to connect to host")
        request = "GET "+path+" HTTP/1.1\r\nHost: "+domain+"\r\n\r\n"
        try:
            self.send(bytes(request, 'utf-8'))
        except RuntimeError:
            raise
        reply = self.receive(timeout=10).split(b'\r\n')
        if self._debug:
            print(reply)
        try:
            headerbreak = reply.index(b'')
        except ValueError:
            raise RuntimeError("Reponse wasn't valid HTML")
        header = reply[0:headerbreak]
        data = b'\r\n'.join(reply[headerbreak+1:])  # put back the way it was
        self.disconnect()
        return (header, data)

    def receive(self, timeout=5):
        """Check for incoming data over the open socket, returns bytes"""
        incoming_bytes = None
        response = b''
        stamp = time.monotonic()
        while (time.monotonic() - stamp) < timeout:
            if self._uart.in_waiting:
                if not incoming_bytes:
                    # read one byte at a time
                    response += self._uart.read(1)
                    # look for the IPD message
                    if (b'+IPD,' in response) and chr(response[-1]) == ':':
                        i = response.index(b'+IPD,')
                        try:
                            incoming_bytes = int(response[i+5:-1])
                        except ValueError:
                            raise RuntimeError("Parsing error during receive")
                        response = b''  # reset the input buffer
                else:
                    # read as much as we can!
                    response += self._uart.read(self._uart.in_waiting)
                    if len(response) >= incoming_bytes:
                        break
        if len(response) == incoming_bytes:
            return response
        raise RuntimeError("Failed to read proper # of bytes")

    def send(self, buffer, timeout=1):
        """Send data over the already-opened socket, buffer must be bytes"""
        cmd = "AT+CIPSEND=%d" % len(buffer)
        self.at_response(cmd, timeout=5, retries=1)
        prompt = b''
        stamp = time.monotonic()
        while (time.monotonic() - stamp) < timeout:
            if self._uart.in_waiting:
                prompt += self._uart.read(1)
                #print(prompt)
                if prompt[-1:] == b'>':
                    break
        if not prompt or (prompt[-1:] != b'>'):
            raise RuntimeError("Didn't get data prompt for sending")
        self._uart.reset_input_buffer()
        self._uart.write(buffer)
        stamp = time.monotonic()
        response = b''
        while (time.monotonic() - stamp) < timeout:
            if self._uart.in_waiting:
                response += self._uart.read(self._uart.in_waiting)
                if response[-9:] == b'SEND OK\r\n':
                    break
                if response[-7:] == b'ERROR\r\n':
                    break
        if self._debug:
            print("<---", response)
        # Get newlines off front and back, then split into lines
#        response = response.strip(b'\r\n').split(b'\r\n')
#        if len(response) < 3:
#            raise RuntimeError("Failed to send data:"+response)
#        if response[0] != bytes("Recv %d bytes" % len(buffer), 'utf-8'):
#            raise RuntimeError("Failed to send data:"+response[0])
#        if response[2] != b'SEND OK':
#            raise RuntimeError("Failed to send data:"+response[2])
        return True

    def disconnect(self):
        """Close any open socket, if there is one"""
        try:
            self.at_response("AT+CIPCLOSE", retries=1)
        except RuntimeError:
            pass  # this is ok, means we didn't have an open po

    def connect(self, conntype, remote, remote_port, *, keepalive=60, retries=1):
        """Open a socket. conntype can be TYPE_TCP, TYPE_UDP, or TYPE_SSL. Remote
        can be an IP address or DNS (we'll do the lookup for you. Remote port
        is integer port on other side. We can't set the local port"""
        # lets just do one connection at a time for now
        self.disconnect()
        self.at_response("AT+CIPMUX=0")
        self.disconnect()
        if not conntype in (self.TYPE_TCP, self.TYPE_UDP, self.TYPE_SSL):
            raise RuntimeError("Connection type must be TCP, UDL or SSL")
        cmd = 'AT+CIPSTART="'+conntype+'","'+remote+'",'+str(remote_port)+','+str(keepalive)
        reply = self.at_response(cmd, timeout=3, retries=retries).strip(b'\r\n')
        if reply == b'CONNECT':
            return True
        return False

    @property
    def mode(self):
        """What mode we're in, can be MODE_STATION, MODE_SOFTAP or MODE_SOFTAPSTATION"""
        reply = self.at_response("AT+CWMODE?", timeout=5).strip(b'\r\n')
        if not reply.startswith(b'+CWMODE:'):
            raise RuntimeError("Bad response to CWMODE?")
        return int(reply[8:])

    @mode.setter
    def mode(self, mode):
        """Station or AP mode selection, can be MODE_STATION, MODE_SOFTAP or MODE_SOFTAPSTATION"""
        if not mode in (1, 2, 3):
            raise RuntimeError("Invalid Mode")
        self.at_response("AT+CWMODE=%d" % mode, timeout=3)

    @property
    def local_ip(self):
        """Our local IP address as a dotted-octal string"""
        reply = self.at_response("AT+CIFSR").strip(b'\r\n')
        for line in reply.split(b'\r\n'):
            if line and line.startswith(b'+CIFSR:STAIP,"'):
                return str(line[14:-1], 'utf-8')
        raise RuntimeError("Couldn't find IP address")

    @property
    def remote_AP(self): # pylint: disable=invalid-name
        """The name of the access point we're connected to, as a string"""
        reply = self.at_response('AT+CWJAP?', timeout=10).strip(b'\r\n')
        if not reply.startswith('+CWJAP:'):
            return [None]*4
        reply = reply[7:].split(b',')
        for i, val in enumerate(reply):
            reply[i] = str(val, 'utf-8')
            try:
                reply[i] = int(reply[i])
            except ValueError:
                reply[i] = reply[i].strip('\"') # its a string!
        return reply

    def join_AP(self, ssid, password): # pylint: disable=invalid-name
        """Try to join an access point by name and password, will return
        immediately if we're already connected and won't try to reconnect"""
        # First make sure we're in 'station' mode so we can connect to AP's
        if self.mode != self.MODE_STATION:
            self.mode = self.MODE_STATION

        router = self.remote_AP
        if router and router[0] == ssid:
            return  # we're already connected!
        reply = self.at_response('AT+CWJAP="'+ssid+'","'+password+'"', timeout=10)
        if "WIFI CONNECTED" not in reply:
            raise RuntimeError("Couldn't connect to WiFi")
        if "WIFI GOT IP" not in reply:
            raise RuntimeError("Didn't get IP address")

    def scan_APs(self, retries=3): # pylint: disable=invalid-name
        """Ask the module to scan for access points and return a list of lists
        with name, RSSI, MAC addresses, etc"""
        for _ in range(retries):
            try:
                scan = self.at_response("AT+CWLAP", timeout=3).split(b'\r\n')
            except RuntimeError:
                continue
            routers = []
            for line in scan:
                if line.startswith(b'+CWLAP:('):
                    router = line[8:-1].split(b',')
                    for i, val in enumerate(router):
                        router[i] = str(val, 'utf-8')
                        try:
                            router[i] = int(router[i])
                        except ValueError:
                            router[i] = router[i].strip('\"') # its a string!
                    routers.append(router)
            return routers

    def at_response(self, at_cmd, timeout=5, retries=3):
        """Send an AT command, check that we got an OK response,
        and then cut out the reply lines to return. We can set
        a variable timeout (how long we'll wait for response) and
        how many times to retry before giving up"""
        for _ in range(retries):
            self._uart.reset_input_buffer()
            if self._debug:
                print("--->", at_cmd)
            #self._uart.reset_input_buffer()
            self._uart.write(bytes(at_cmd, 'utf-8'))
            self._uart.write(b'\x0d\x0a')
            #uart.timeout = timeout
            #print(uart.readline())  # read echo and toss
            stamp = time.monotonic()
            response = b''
            while (time.monotonic() - stamp) < timeout:
                if self._uart.in_waiting:
                    response += self._uart.read(self._uart.in_waiting)
                    if response[-4:] == b'OK\r\n':
                        break
                    if response[-7:] == b'ERROR\r\n':
                        break
            # eat beginning \n and \r
            if self._debug:
                print("<---", response)
            if response[-4:] != b'OK\r\n':
                time.sleep(1)
                continue
            return response[:-4]
        raise RuntimeError("No OK response to "+at_cmd)

    def get_version(self):
        """Request the AT firmware version string and parse out the
        version number"""
        reply = self.at_response("AT+GMR", timeout=1).strip(b'\r\n')
        for line in reply.split(b'\r\n'):
            if line:
                self._versionstrings.append(str(line, 'utf-8'))
        # get the actual version out
        vers = self._versionstrings[0].split('(')[0]
        if not vers.startswith('AT version:'):
            return False
        self._version = vers[11:]
        return self._version

    def sync(self):
        """Check if we have AT commmand sync by sending plain ATs"""
        try:
            self.at_response("AT", timeout=1)
            return True
        except RuntimeError:
            return False

    def echo(self, echo):
        """Set AT command echo on or off"""
        if echo:
            self.at_response("ATE1", timeout=1)
        else:
            self.at_response("ATE0", timeout=1)

    def soft_reset(self):
        """Perform a software reset by AT command. Returns True
        if we successfully performed, false if failed to reset"""
        try:
            self._uart.reset_input_buffer()
            reply = self.at_response("AT+RST", timeout=1)
            if reply.strip(b'\r\n') == b'AT+RST':
                time.sleep(2)
                self._uart.reset_input_buffer()
                return True
        except RuntimeError:
            pass # fail, see below
        return False

    def hard_reset(self):
        """Perform a hardware reset by toggling the reset pin, if it was
        defined in the initialization of this object"""
        if self._reset_pin:
            self._reset_pin.direction = Direction.OUTPUT
            self._reset_pin.value = False
            time.sleep(0.1)
            self._reset_pin.value = True
            time.sleep(1)
            self._uart.reset_input_buffer()
