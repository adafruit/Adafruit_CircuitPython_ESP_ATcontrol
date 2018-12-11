import os
import time
from digitalio import DigitalInOut, Direction, Pull

class espatcommands:

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
        # Connect and sync
        if not self.sync():
            if not self.soft_reset():
                self.hard_reset()
                self.soft_reset()
        self.echo(False)

    def request_url(self, url, ssl=False):
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
        reply = self.receive(timeout=5).split(b'\r\n')
        if self._debug:
            print(reply)
        headerbreak = reply.index(b'')
        header = reply[0:headerbreak]
        data = b'\r\n'.join(reply[headerbreak+1:])  # put back the way it was
        self.disconnect()
        return (header, data)

    def receive(self, timeout=5):
        incoming_bytes = None
        response = b''
        t = time.monotonic()
        while (time.monotonic() - t) < timeout:
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

    def send(self, buffer, timeout=0.5):
        cmd = "AT+CIPSEND=%d" % len(buffer)
        self.at_response(cmd, timeout=0.1, retries=1)
        prompt = self._uart.read(2)
        if not prompt or prompt != b'> ':
            raise RuntimeError("Didn't get data prompt for sending")
        self._uart.write(buffer)
        t = time.monotonic()
        response = b''
        while (time.monotonic() - t) < timeout:
            if self._uart.in_waiting:
                response += self._uart.read(1)
                if response[-9:] == b'SEND OK\r\n':
                    break
                if response[-7:] == b'ERROR\r\n':
                    break
        if self._debug:
            print("<---", response)
        # Get newlines off front and back, then split into lines
        response = response.strip(b'\r\n').split(b'\r\n')
        if response[0] != bytes("Recv %d bytes" % len(buffer), 'utf-8'):
            raise RuntimeError("Failed to send data:"+response[0])
        if response[2] != b'SEND OK':
            raise RuntimeError("Failed to send data:"+response[2])
        return True

    def disconnect(self):
        try:
            self.at_response("AT+CIPCLOSE", retries=1)
        except RuntimeError:
            pass  # this is ok, means we didn't have an open po

    def connect(self, type, remote, remote_port, *, keepalive=60, retries=1):
        # lets just do one connection at a time for now
        self.disconnect()
        self.at_response("AT+CIPMUX=0")
        self.disconnect()
        if not type in (self.TYPE_TCP, self.TYPE_UDP, self.TYPE_SSL):
            raise RuntimeError("Connection type must be TCP, UDL or SSL")
        cmd = 'AT+CIPSTART="'+type+'","'+remote+'",'+str(remote_port)+','+str(keepalive)
        reply = self.at_response(cmd, timeout=3, retries=retries).strip(b'\r\n')
        if reply == b'CONNECT':
            return True
        return False

    @property
    def mode(self):
        reply = self.at_response("AT+CWMODE?", timeout=5).strip(b'\r\n')
        if not reply.startswith(b'+CWMODE:'):
            raise RuntimeError("Bad response")
        return int(reply[8:])

    @mode.setter
    def mode(self, mode):
        if not mode in (1, 2, 3):
            raise RuntimeError("Invalid Mode")
        self.at_response("AT+CWMODE=%d" % mode, timeout=3)

    @property
    def local_ip(self):
        reply = self.at_response("AT+CIFSR").strip(b'\r\n')
        for s in reply.split(b'\r\n'):
            if s and s.startswith(b'+CIFSR:STAIP,"'):
                return str(s[14:-1],'utf-8')
        raise RuntimeError("Couldn't find IP address")

    @property
    def remote_AP(self):
        reply = self.at_response('AT+CWJAP?', timeout=10).strip(b'\r\n')
        if not reply.startswith('+CWJAP:'):
            return [None]*4
        reply = reply[7:].split(b',')
        for i, val in enumerate(reply):
            reply[i] = str(val,'utf-8')
            try:
                reply[i] = int(reply[i])
            except ValueError:
                reply[i] = reply[i].strip('\"') # its a string!
        return reply

    def join_AP(self, ssid, password):
        # First make sure we're in 'station' mode so we can connect to AP's
        if self.mode != self.MODE_STATION:
            self.mode = self.MODE_STATION

        AP = self.remote_AP
        if AP and AP[0] == ssid:
            return  # we're already connected!
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
            self._uart.reset_input_buffer()
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
                if self._uart.in_waiting:
                    response += self._uart.read(1)
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
        raise RuntimeError("Not OK")

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

    def sync(self):
        try:
            self.at_response("AT", timeout=0.1)
            return True
        except RuntimeError:
            return False

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
        except RuntimeError:
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
