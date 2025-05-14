# SPDX-FileCopyrightText: 2018 ladyada for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_espatcontrol.adafruit_espatcontrol`
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

import gc
import time

from digitalio import DigitalInOut, Direction

try:
    from typing import Dict, List, Optional, Union

    import busio
except ImportError:
    pass

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_espATcontrol.git"


class OKError(Exception):
    """The exception thrown when we didn't get acknowledgement to an AT command"""


class ESP_ATcontrol:
    """A wrapper for AT commands to a connected ESP8266 or ESP32 module to do
    some very basic internetting. The ESP module must be pre-programmed with
    AT command firmware, you can use esptool or our CircuitPython miniesptool
    to upload firmware"""

    MODE_STATION = 1
    MODE_SOFTAP = 2
    MODE_SOFTAPSTATION = 3
    TYPE_TCP = "TCP"
    TCP_MODE = "TCP"
    TYPE_UDP = "UDP"
    TYPE_SSL = "SSL"
    TLS_MODE = "SSL"
    STATUS_APCONNECTED = 2  # CIPSTATUS method
    STATUS_WIFI_APCONNECTED = 2  # CWSTATE method
    STATUS_SOCKETOPEN = 3  # CIPSTATUS method
    STATUS_SOCKET_OPEN = 3  # CIPSTATE method
    STATUS_SOCKETCLOSED = 4  # CIPSTATUS method
    STATUS_SOCKET_CLOSED = 4  # CIPSTATE method
    STATUS_NOTCONNECTED = 5  # CIPSTATUS method
    STATUS_WIFI_NOTCONNECTED = 1  # CWSTATE method
    STATUS_WIFI_DISCONNECTED = 4  # CWSTATE method

    USER_AGENT = "esp-idf/1.0 esp32"

    def __init__(
        self,
        uart: busio.UART,
        default_baudrate: int,
        *,
        run_baudrate: Optional[int] = None,
        rts_pin: Optional[DigitalInOut] = None,
        reset_pin: Optional[DigitalInOut] = None,
        debug: bool = False,
        use_cipstatus: bool = False,
    ):
        """This function doesn't try to do any sync'ing, just sets up
        # the hardware, that way nothing can unexpectedly fail!"""
        self._uart = uart
        if not run_baudrate:
            run_baudrate = default_baudrate
        self._default_baudrate = default_baudrate
        self._run_baudrate = run_baudrate
        self._uart.baudrate = default_baudrate

        self._reset_pin = reset_pin
        self._rts_pin = rts_pin
        if self._reset_pin:
            self._reset_pin.direction = Direction.OUTPUT
            self._reset_pin.value = True
        if self._rts_pin:
            self._rts_pin.direction = Direction.OUTPUT
        self.hw_flow(True)

        self._debug = debug
        self._versionstrings = []
        self._version = None
        self._ipdpacket = bytearray(1500)
        self._ifconfig = []
        self._initialized = False
        self._conntype = None
        self._use_cipstatus = use_cipstatus

    def begin(self) -> None:
        """Initialize the module by syncing, resetting if necessary, setting up
        the desired baudrate, turning on single-socket mode, and configuring
        SSL support. Required before using the module but we dont do in __init__
        because this can throw an exception."""
        # Connect and sync
        for _ in range(3):
            try:
                if not self.sync() and not self.soft_reset():
                    self.hard_reset()
                    self.soft_reset()
                self.echo(False)
                # set flow control if required
                self.baudrate = self._run_baudrate
                # get and cache versionstring
                self.get_version()
                if self.cipmux != 0:
                    self.cipmux = 0
                try:
                    self.at_response("AT+CIPSSLSIZE=4096", retries=1, timeout=3)
                except OKError:
                    # ESP32 doesnt use CIPSSLSIZE, its ok!
                    self.at_response("AT+CIPSSLCCONF?")

                try:
                    self.at_response("AT+CWSTATE?", retries=1, timeout=3)
                except OKError:
                    # ESP8285's use CIPSTATUS and have no CWSTATE or CWIPSTATUS functions
                    self._use_cipstatus = True
                    if self._debug:
                        print("No CWSTATE support, using CIPSTATUS, it's ok!")

                self._initialized = True
                return
            except OKError:
                pass  # retry

    def connect(
        self, secrets: Dict[str, Union[str, int]], timeout: int = 15, retries: int = 3
    ) -> None:
        """Repeatedly try to connect to an access point with the details in
        the passed in 'secrets' dictionary. Be sure 'ssid' and 'password' are
        defined in the secrets dict! If 'timezone' is set, we'll also configure
        SNTP"""
        # Connect to WiFi if not already
        try:
            if not self._initialized:
                self.begin()
            AP = self.remote_AP
            if AP[0] != secrets["ssid"]:
                self.join_AP(
                    secrets["ssid"],
                    secrets["password"],
                    timeout=timeout,
                    retries=retries,
                )
                print("Connected to", secrets["ssid"])
                if "timezone" in secrets:
                    tzone = secrets["timezone"]
                    ntp = None
                    if "ntp_server" in secrets:
                        ntp = secrets["ntp_server"]
                    self.sntp_config(True, tzone, ntp)
                print("My IP Address:", self.local_ip)
            else:
                print("Already connected to", AP[0])
            return  # yay!
        except (RuntimeError, OKError) as exp:
            print("Failed to connect\n", exp)
            raise

    def connect_enterprise(
        self, secrets: Dict[str, Union[str, int]], timeout: int = 15, retries: int = 3
    ) -> None:
        """Repeatedly try to connect to an enterprise access point with the details in
        the passed in 'secrets' dictionary. Be sure 'ssid','password','username','identity'
        and 'method' are defined in the secrets dict! If 'timezone' is set, we'll also
        configure SNTP"""
        # Connect to WiFi if not already
        retries = 3
        if self._debug:
            print("In connect_enterprise()")
        while True:
            try:
                if not self._initialized or retries == 0:
                    self.begin()
                retries = 3
                AP = self.remote_AP
                if AP[0] is not None:
                    print("Connected to", AP[0])
                if AP[0] != secrets["ssid"]:
                    if self._debug:
                        print("Doing Enterprise connection sequence")
                    self.join_AP_Enterprise(
                        secrets["ssid"],
                        secrets["username"],
                        secrets["identity"],
                        secrets["password"],
                        secrets["method"],
                        timeout=timeout,
                        retries=retries,
                    )
                    if "timezone" in secrets:
                        tzone = secrets["timezone"]
                        ntp = None
                        if "ntp_server" in secrets:
                            ntp = secrets["ntp_server"]
                        self.sntp_config(True, tzone, ntp)
                    print("Connected to", self.remote_AP[0])
                    print("My IP Address:", self.local_ip)
                return  # yay!
            except (RuntimeError, OKError) as exp:
                print("Failed to connect, retrying\n", exp)
                retries -= 1
                continue

    def set_autoconnect(self, autoconnect: bool) -> None:
        """Set the auto connection status if the wifi connects automatically on powerup"""
        if autoconnect is True:
            auto_flag = "1"
        else:
            auto_flag = "0"
        self.at_response("AT+CWAUTOCONN=" + auto_flag)

    # *************************** SOCKET SETUP ****************************

    @property
    def cipmux(self) -> int:
        """The IP socket multiplexing setting. 0 for one socket, 1 for multi-socket"""
        replies = self.at_response("AT+CIPMUX?", timeout=3).split(b"\r\n")
        for reply in replies:
            if reply.startswith(b"+CIPMUX:"):
                return int(reply[8:])
        raise RuntimeError("Bad response to CIPMUX?")

    def socket_connect(
        self,
        conntype: str,
        remote: str,
        remote_port: int,
        *,
        keepalive: int = 10,
        retries: int = 1,
    ) -> bool:
        """Open a socket. conntype can be TYPE_TCP, TYPE_UDP, or TYPE_SSL. Remote
        can be an IP address or DNS (we'll do the lookup for you. Remote port
        is integer port on other side. We can't set the local port.

        Note that this method is usually called by the requests-package, which
        does not know anything about conntype. So it is mandatory to set
        the conntype manually before calling this method if the conntype-parameter
        is not provided.

        If requests are done using ESPAT_WiFiManager, the conntype is set there
        depending on the protocol (http/https)."""

        # if caller does not provide conntype, use default conntype from
        # object if set, otherwise fall back to old buggy logic
        if not conntype and self._conntype:
            conntype = self._conntype
        elif not conntype:
            # old buggy code from espatcontrol_socket
            # added here for compatibility with old code
            if remote_port == 80:
                conntype = self.TYPE_TCP
            elif remote_port == 443:
                conntype = self.TYPE_SSL
            # to cater for MQTT over TCP
            elif remote_port == 1883:
                conntype = self.TYPE_TCP

        # lets just do one connection at a time for now
        if conntype == self.TYPE_UDP:
            # always disconnect for TYPE_UDP
            self.socket_disconnect()
        while True:
            stat = self.status
            if stat in {self.STATUS_APCONNECTED, self.STATUS_SOCKETCLOSED}:
                break
            if stat == self.STATUS_SOCKETOPEN:
                self.socket_disconnect()
            else:
                time.sleep(1)
        if conntype not in {self.TYPE_TCP, self.TYPE_UDP, self.TYPE_SSL}:
            raise RuntimeError("Connection type must be TCP, UDL or SSL")
        cmd = (
            'AT+CIPSTART="'
            + conntype
            + '","'
            + remote
            + '",'
            + str(remote_port)
            + ","
            + str(keepalive)
        )
        if self._debug is True:
            print("socket_connect(): Going to send command")
        replies = self.at_response(cmd, timeout=10, retries=retries).split(b"\r\n")
        for reply in replies:
            if reply == b"CONNECT" and (
                conntype in {self.TYPE_TCP, self.TYPE_SSL}
                and self.status == self.STATUS_SOCKETOPEN
                or conntype == self.TYPE_UDP
            ):
                self._conntype = conntype
                return True

        return False

    def socket_send(self, buffer: bytes, timeout: int = 1) -> bool:
        """Send data over the already-opened socket, buffer must be bytes"""
        cmd = "AT+CIPSEND=%d" % len(buffer)
        self.at_response(cmd, timeout=5, retries=1)
        prompt = b""
        stamp = time.monotonic()
        while (time.monotonic() - stamp) < timeout:
            if self._uart.in_waiting:
                prompt += self._uart.read(1)
                self.hw_flow(False)
                # print(prompt)
                if prompt[-1:] == b">":
                    break
            else:
                self.hw_flow(True)
        if not prompt or (prompt[-1:] != b">"):
            raise RuntimeError("Didn't get data prompt for sending")
        self._uart.reset_input_buffer()
        self._uart.write(buffer)
        if self._conntype == self.TYPE_UDP:
            return True
        stamp = time.monotonic()
        response = b""
        while (time.monotonic() - stamp) < timeout:
            if self._uart.in_waiting:
                response += self._uart.read(self._uart.in_waiting)
                if response[-9:] == b"SEND OK\r\n":
                    break
                if response[-7:] == b"ERROR\r\n":
                    break
        if self._debug:
            print("<---", response)
        # Get newlines off front and back, then split into lines
        return True

    def socket_receive(self, timeout: int = 5) -> bytearray:
        """Check for incoming data over the open socket, returns bytes"""
        incoming_bytes = None
        bundle = []
        toread = 0
        gc.collect()
        i = 0  # index into our internal packet
        stamp = time.monotonic()
        ipd_start = b"+IPD,"
        while (time.monotonic() - stamp) < timeout:
            if self._uart.in_waiting:
                stamp = time.monotonic()  # reset timestamp when there's data!
                if not incoming_bytes:
                    self.hw_flow(False)  # stop the flow
                    # read one byte at a time
                    self._ipdpacket[i] = self._uart.read(1)[0]
                    if chr(self._ipdpacket[0]) != "+":
                        i = 0  # keep goin' till we start with +
                        continue
                    i += 1
                    # look for the IPD message
                    if (ipd_start in self._ipdpacket) and chr(self._ipdpacket[i - 1]) == ":":
                        try:
                            ipd = str(self._ipdpacket[5 : i - 1], "utf-8")
                            incoming_bytes = int(ipd)
                            if self._debug:
                                print("Receiving:", incoming_bytes)
                        except ValueError as err:
                            raise RuntimeError("Parsing error during receive", ipd) from err
                        i = 0  # reset the input buffer now that we know the size
                    elif i > 20:
                        i = 0  # Hmm we somehow didnt get a proper +IPD packet? start over
                else:
                    self.hw_flow(False)  # stop the flow
                    # read as much as we can!
                    toread = min(incoming_bytes - i, self._uart.in_waiting)
                    # print("i ", i, "to read:", toread)
                    self._ipdpacket[i : i + toread] = self._uart.read(toread)
                    i += toread
                    if i == incoming_bytes:
                        # print(self._ipdpacket[0:i])
                        gc.collect()
                        bundle.append(self._ipdpacket[0:i])
                        gc.collect()
                        i = incoming_bytes = 0
                        break  # We've received all the data. Don't wait until timeout.
            else:  # no data waiting
                self.hw_flow(True)  # start the floooow
        totalsize = sum(len(x) for x in bundle)
        ret = bytearray(totalsize)
        i = 0
        for x in bundle:
            for char in x:
                ret[i] = char
                i += 1
        del bundle
        gc.collect()
        return ret

    def socket_disconnect(self) -> None:
        """Close any open socket, if there is one"""
        self._conntype = None
        try:
            self.at_response("AT+CIPCLOSE", retries=1)
        except OKError:
            pass  # this is ok, means we didn't have an open socket

    # *************************** SNTP SETUP ****************************

    def sntp_config(
        self, enable: bool, timezone: Optional[int] = None, server: Optional[str] = None
    ) -> None:
        """Configure the built in ESP SNTP client with a UTC-offset number (timezone)
        and server as IP or hostname."""
        cmd = "AT+CIPSNTPCFG="
        if enable:
            cmd += "1"
        else:
            cmd += "0"
        if timezone is not None:
            cmd += ",%d" % timezone
        if server is not None:
            cmd += ',"%s"' % server
        self.at_response(cmd, timeout=3)

    @property
    def sntp_time(self) -> Union[bytes, None]:
        """Return a string with time/date information using SNTP, may return
        1970 'bad data' on the first few minutes, without warning!"""
        replies = self.at_response("AT+CIPSNTPTIME?", timeout=5).split(b"\r\n")
        for reply in replies:
            if reply.startswith(b"+CIPSNTPTIME:"):
                return reply[13:]
        return None

    # *************************** WIFI SETUP ****************************

    @property
    def is_connected(self) -> bool:
        """Initialize module if not done yet, and check if we're connected to
        an access point, returns True or False"""
        if not self._initialized:
            self.begin()
        try:
            self.echo(False)
            self.baudrate = self.baudrate
            stat = self.status
            if stat in {
                self.STATUS_APCONNECTED,
                self.STATUS_SOCKETOPEN,
                self.STATUS_SOCKETCLOSED,
            }:
                if self._debug:
                    print("is_connected(): status says connected")
                return True
        except (OKError, RuntimeError):
            pass
        if self._debug:
            print("is_connected(): status says not connected")
        return False

    @property
    def status(self) -> Union[int, None]:
        """The IP connection status number (see AT+CIPSTATUS datasheet for meaning)"""
        if self._use_cipstatus:
            replies = self.at_response("AT+CIPSTATUS", timeout=5).split(b"\r\n")
            for reply in replies:
                if reply.startswith(b"STATUS:"):
                    if self._debug:
                        print(f"CIPSTATUS state is {int(reply[7:8])}")
                    return int(reply[7:8])
        else:
            status_w = self.status_wifi
            status_s = self.status_socket

            # debug only, Check CIPSTATUS messages against CWSTATE/CIPSTATE
            if self._debug:
                replies = self.at_response("AT+CIPSTATUS", timeout=5).split(b"\r\n")
                for reply in replies:
                    if reply.startswith(b"STATUS:"):
                        cipstatus = int(reply[7:8])
                print(f"STATUS: CWSTATE: {status_w}, CIPSTATUS: {cipstatus}, CIPSTATE: {status_s}")

            # Produce a cipstatus-compatible status code
            # Codes are not the same between CWSTATE/CIPSTATUS so in some combinations
            # we just pick what we hope is best.
            if status_w in {
                self.STATUS_WIFI_NOTCONNECTED,
                self.STATUS_WIFI_DISCONNECTED,
            }:
                if self._debug:
                    print(f"STATUS returning {self.STATUS_NOTCONNECTED}")
                return self.STATUS_NOTCONNECTED

            if status_s == self.STATUS_SOCKET_OPEN:
                if self._debug:
                    print(f"STATUS returning {self.STATUS_SOCKETOPEN}")
                return self.STATUS_SOCKETOPEN

            if status_w == self.STATUS_WIFI_APCONNECTED:
                if self._debug:
                    print(f"STATUS returning {self.STATUS_APCONNECTED}")
                return self.STATUS_APCONNECTED

            # handle extra codes from CWSTATE
            if status_w == 0:  # station has not started any Wi-Fi connection.
                if self._debug:
                    print("STATUS returning 1")
                return 1  # this cipstatus had no previous handler variable

            if (
                status_w == 1
            ):  # station has connected to an AP, but does not get an IPv4 address yet.
                if self._debug:
                    print("STATUS returning 1")
                return 1  # this cipstatus had no previous handler variable

            if status_w == 3:  # station is in Wi-Fi connecting or reconnecting state.
                if self._debug:
                    print(f"STATUS returning {self.STATUS_NOTCONNECTED}")
                return self.STATUS_NOTCONNECTED

            if status_s == self.STATUS_SOCKET_CLOSED:
                if self._debug:
                    print(f"STATUS returning {self.STATUS_SOCKET_CLOSED}")
                return self.STATUS_SOCKET_CLOSED

        return None

    @property
    def status_wifi(self) -> Union[int, None]:
        """The WIFI connection status number (see AT+CWSTATE datasheet for meaning)"""
        replies = self.at_response("AT+CWSTATE?", timeout=5).split(b"\r\n")
        for reply in replies:
            if reply.startswith(b"+CWSTATE:"):
                state_info = reply.split(b",")
                if self._debug:
                    print(f"State reply is {reply}, state_info[1] is {int(state_info[0][9:10])}")
                return int(state_info[0][9:10])
        return None

    @property
    def status_socket(self) -> Union[int, None]:
        """The Socket connection status number (see AT+CIPSTATE for meaning)"""
        replies = self.at_response("AT+CIPSTATE?", timeout=5).split(b"\r\n")
        for reply in replies:
            # If there are any +CIPSTATE lines that means it's an open socket
            if reply.startswith(b"+CIPSTATE:"):
                return self.STATUS_SOCKET_OPEN
        return self.STATUS_SOCKET_CLOSED

    @property
    def mode(self) -> Union[int, None]:
        """What mode we're in, can be MODE_STATION, MODE_SOFTAP or MODE_SOFTAPSTATION"""
        if not self._initialized:
            self.begin()
        replies = self.at_response("AT+CWMODE?", timeout=5).split(b"\r\n")
        for reply in replies:
            if reply.startswith(b"+CWMODE:"):
                return int(reply[8:])
        raise RuntimeError("Bad response to CWMODE?")

    @mode.setter
    def mode(self, mode: int) -> None:
        """Station or AP mode selection, can be MODE_STATION, MODE_SOFTAP or MODE_SOFTAPSTATION"""
        if not self._initialized:
            self.begin()
        if mode not in {1, 2, 3}:
            raise RuntimeError("Invalid Mode")
        self.at_response("AT+CWMODE=%d" % mode, timeout=3)

    @property
    def conntype(self) -> Union[str, None]:
        """The configured connection-type"""
        return self._conntype

    @conntype.setter
    def conntype(self, conntype: str) -> None:
        """set connection-type for subsequent socket_connect()"""
        self._conntype = conntype

    @property
    def local_ip(self) -> Union[str, None]:
        """Our local IP address as a dotted-quad string"""
        reply = self.at_response("AT+CIFSR").strip(b"\r\n")
        for line in reply.split(b"\r\n"):
            if line and line.startswith(b'+CIFSR:STAIP,"'):
                return str(line[14:-1], "utf-8")
        raise RuntimeError("Couldn't find IP address")

    def ping(self, host: str) -> Union[int, None]:
        """Ping the IP or hostname given, returns ms time or None on failure"""
        reply = self.at_response('AT+PING="%s"' % host.strip('"'), timeout=5)
        for line in reply.split(b"\r\n"):
            if line and line.startswith(b"+"):
                try:
                    if line[1:5] == b"PING":
                        return int(line[6:])
                    return int(line[1:])
                except ValueError:
                    return None
        raise RuntimeError("Couldn't ping")

    def nslookup(self, host: str) -> Union[str, None]:
        """Return a dotted-quad IP address strings that matches the hostname"""
        reply = self.at_response('AT+CIPDOMAIN="%s"' % host.strip('"'), timeout=3)
        for line in reply.split(b"\r\n"):
            if line and line.startswith(b"+CIPDOMAIN:"):
                return str(line[11:], "utf-8").strip('"')
        raise RuntimeError("Couldn't find IP address")

    # *************************** AP SETUP ****************************

    @property
    def remote_AP(self) -> List[Union[int, str, None]]:
        """The name of the access point we're connected to, as a string"""
        stat = self.status
        if stat != self.STATUS_APCONNECTED:
            return [None] * 4
        replies = self.at_response("AT+CWJAP?", timeout=10).split(b"\r\n")
        for reply in replies:
            if not reply.startswith("+CWJAP:"):
                continue
            reply = reply[7:].split(b",")
            for i, val in enumerate(reply):
                reply[i] = str(val, "utf-8")
                try:
                    reply[i] = int(reply[i])
                except ValueError:
                    reply[i] = reply[i].strip('"')  # its a string!
            return reply
        return [None] * 4

    def join_AP(self, ssid: str, password: str, timeout: int = 15, retries: int = 3) -> None:
        """Try to join an access point by name and password, will return
        immediately if we're already connected and won't try to reconnect"""
        # First make sure we're in 'station' mode so we can connect to AP's
        if self._debug:
            print("In join_AP()")
        if self.mode != self.MODE_STATION:
            self.mode = self.MODE_STATION

        router = self.remote_AP
        if router and router[0] == ssid:
            return  # we're already connected!
        reply = self.at_response(
            'AT+CWJAP="' + ssid + '","' + password + '"',
            timeout=timeout,
            retries=retries,
        )
        if b"WIFI CONNECTED" not in reply:
            print("no CONNECTED")
            raise RuntimeError("Couldn't connect to WiFi")
        if b"WIFI GOT IP" not in reply:
            print("no IP")
            raise RuntimeError("Didn't get IP address")
        return

    def join_AP_Enterprise(
        self,
        ssid: str,
        username: str,
        identity: str,
        password: str,
        method: int,
        timeout: int = 30,
        retries: int = 3,
    ) -> None:
        """Try to join an Enterprise access point by name and password, will return
        immediately if we're already connected and won't try to reconnect"""
        # Not sure how to verify certificates so we set that to not verify.
        certificate_security = 0  # Bit0: Client certificate.Bit1: Server certificate.

        if self._debug:
            print("In join_AP_Enterprise()")
        if self.mode != self.MODE_STATION:
            self.mode = self.MODE_STATION

        router = self.remote_AP
        if router and router[0] == ssid:
            return  # we're already connected!
        reply = self.at_response(
            'AT+CWJEAP="'
            + ssid
            + '",'
            + str(method)
            + ',"'
            + identity
            + '","'
            + username
            + '","'
            + password
            + '",'
            + str(certificate_security),
            timeout=timeout,
            retries=retries,
        )
        if b"WIFI CONNECTED" not in reply:
            print("no CONNECTED")
            raise RuntimeError("Couldn't connect to Enterprise WiFi")
        if b"WIFI GOT IP" not in reply:
            print("no IP")
            raise RuntimeError("Didn't get IP address")
        return

    def disconnect(self, timeout: int = 5, retries: int = 3):
        """Disconnect from the AP. Tries whether connected or not."""
        # If we're not connected we likely don't get a "WIFI DISCONNECT" and just get the OK
        # Note it still tries to disconnect even if it says we're not connected.
        if not self._initialized:
            self.begin()
        stat = self.status
        if stat in {
            self.STATUS_APCONNECTED,
            self.STATUS_SOCKETOPEN,
            self.STATUS_SOCKETCLOSED,
        }:
            wait_for_disconnect = True
        else:
            wait_for_disconnect = False
            if self._debug is True:
                print("disconnect(): Not connected, not waiting for disconnect message")
        reply = self.at_response("AT+CWQAP", timeout=timeout, retries=retries)
        # Don't bother waiting for disconnect message if we weren't connected already
        # sometimes the "WIFI DISCONNECT" shows up in the reply and sometimes it doesn't.
        if wait_for_disconnect is True:
            if b"WIFI DISCONNECT" in reply:
                if self._debug is True:
                    print(f"disconnect(): Got WIFI DISCONNECT: {reply}")
            else:
                stamp = time.monotonic()
                response = b""
                while (time.monotonic() - stamp) < timeout:
                    if self._uart.in_waiting:
                        response += self._uart.read(1)
                        self.hw_flow(False)
                        if response[-15:] == b"WIFI DISCONNECT":
                            break
                    else:
                        self.hw_flow(True)
                if self._debug:
                    if response[-15:] == b"WIFI DISCONNECT":
                        print(f"disconnect(): Got WIFI DISCONNECT: {response}")
                    else:
                        print(f"disconnect(): Timed out wating for WIFI DISCONNECT: {response}")

    def scan_APs(self, retries: int = 3) -> Union[List[List[bytes]], None]:
        """Ask the module to scan for access points and return a list of lists
        with name, RSSI, MAC addresses, etc"""
        for _ in range(retries):
            try:
                if self.mode != self.MODE_STATION:
                    self.mode = self.MODE_STATION
                scan = self.at_response("AT+CWLAP", timeout=5).split(b"\r\n")
            except RuntimeError:
                continue
            routers = []
            for line in scan:
                if line.startswith(b"+CWLAP:("):
                    router = line[8:-1].split(b",")
                    for i, val in enumerate(router):
                        router[i] = str(val, "utf-8")
                        try:
                            router[i] = int(router[i])
                        except ValueError:
                            router[i] = router[i].strip('"')  # its a string!
                    routers.append(router)
            return routers

    # ************************** AT LOW LEVEL ****************************

    @property
    def version(self) -> Union[str, None]:
        """The cached version string retrieved via the AT+GMR command"""
        return self._version

    def get_version(self) -> Union[str, None]:
        """Request the AT firmware version string and parse out the
        version number"""
        reply = self.at_response("AT+GMR", timeout=3).strip(b"\r\n")
        self._version = None
        for line in reply.split(b"\r\n"):
            if line:
                self._versionstrings.append(str(line, "utf-8"))
                # get the actual version out
                if b"AT version:" in line:
                    self._version = str(line, "utf-8")
        return self._version

    def hw_flow(self, flag: bool) -> None:
        """Turn on HW flow control (if available) on to allow data, or off to stop"""
        if self._rts_pin:
            self._rts_pin.value = not flag

    def at_response(self, at_cmd: str, timeout: int = 5, retries: int = 3) -> bytes:
        """Send an AT command, check that we got an OK response,
        and then cut out the reply lines to return. We can set
        a variable timeout (how long we'll wait for response) and
        how many times to retry before giving up"""
        for _ in range(retries):
            self.hw_flow(True)  # allow any remaning data to stream in
            time.sleep(0.1)  # wait for uart data
            self._uart.reset_input_buffer()  # flush it
            self.hw_flow(False)  # and shut off flow control again
            if self._debug:
                print("--->", at_cmd)
            self._uart.write(bytes(at_cmd, "utf-8"))
            self._uart.write(b"\x0d\x0a")
            stamp = time.monotonic()
            response = b""
            while (time.monotonic() - stamp) < timeout:
                if self._uart.in_waiting:
                    response += self._uart.read(1)
                    self.hw_flow(False)
                    if response[-4:] == b"OK\r\n":
                        break
                    if response[-7:] == b"ERROR\r\n":
                        break
                    if "AT+CWJAP=" in at_cmd or "AT+CWJEAP=" in at_cmd:
                        if b"WIFI GOT IP\r\n" in response:
                            break
                    elif b"WIFI CONNECTED\r\n" in response:
                        break
                    if b"ERR CODE:" in response:
                        break
                else:
                    self.hw_flow(True)
            # eat beginning \n and \r
            if self._debug:
                print("<---", response)
            # special case, AT+CWJAP= does not return an ok :P
            if "AT+CWJAP=" in at_cmd and b"WIFI GOT IP\r\n" in response:
                return response
            # special case, AT+CWJEAP= does not return an ok :P
            if "AT+CWJEAP=" in at_cmd and b"WIFI GOT IP\r\n" in response:
                return response
            if "AT+CWQAP=" in at_cmd and b"WIFI DISCONNECT" in response:
                return response
            # special case, ping also does not return an OK
            if "AT+PING" in at_cmd and b"ERROR\r\n" in response:
                return response
            # special case, does return OK but in fact it is busy
            if "AT+CIFSR" in at_cmd and b"busy" in response or response[-4:] != b"OK\r\n":
                time.sleep(1)
                continue
            return response[:-4]
        raise OKError("No OK response to " + at_cmd)

    def sync(self) -> bool:
        """Check if we have AT commmand sync by sending plain ATs"""
        try:
            self.at_response("AT", timeout=1)
            return True
        except OKError:
            return False

    @property
    def baudrate(self) -> int:
        """The baudrate of our UART connection"""
        return self._uart.baudrate

    @baudrate.setter
    def baudrate(self, baudrate: int) -> None:
        """Change the modules baudrate via AT commands and then check
        that we're still sync'd."""
        at_cmd = "AT+UART_CUR=" + str(baudrate) + ",8,1,0,"
        if self._rts_pin is not None:
            at_cmd += "2"
        else:
            at_cmd += "0"
        at_cmd += "\r\n"
        if self._debug:
            print("Changing baudrate to:", baudrate)
            print("--->", at_cmd)
        self._uart.write(bytes(at_cmd, "utf-8"))
        time.sleep(0.25)
        self._uart.baudrate = baudrate
        time.sleep(0.25)
        self._uart.reset_input_buffer()
        if not self.sync():
            raise RuntimeError("Failed to resync after Baudrate change")

    def echo(self, echo: bool) -> None:
        """Set AT command echo on or off"""
        if echo:
            self.at_response("ATE1", timeout=1)
        else:
            self.at_response("ATE0", timeout=1)

    def soft_reset(self, timeout: int = 5) -> bool:
        """Perform a software reset by AT command. Returns True
        if we successfully performed, false if failed to reset"""
        try:
            self._uart.reset_input_buffer()
            reply = self.at_response("AT+RST", timeout=1)
            if self._debug:
                print(f"Resetting with AT+RST, reply was {reply}")
            stamp = time.monotonic()
            response = b""
            while (time.monotonic() - stamp) < timeout:
                if self._uart.in_waiting:
                    response += self._uart.read(1)
                    self.hw_flow(False)
                    if response[-5:] == b"ready":
                        break
                else:
                    self.hw_flow(True)
            if self._debug:
                if response[-5:] == b"ready":
                    print(f"soft_reset(): Got ready: {response}")
                else:
                    print(f"soft_reset(): imed out waiting for ready: {response}")
            self._uart.reset_input_buffer()
            self.sync()
            return True
        except OKError:
            pass  # fail, see below
        return False

    def factory_reset(self) -> None:
        """Perform a hard reset, then send factory restore settings request"""
        self.hard_reset()
        self.at_response("AT+RESTORE", timeout=1)
        self._initialized = False

    def hard_reset(self) -> None:
        """Perform a hardware reset by toggling the reset pin, if it was
        defined in the initialization of this object"""
        if self._reset_pin:
            self._reset_pin.direction = Direction.OUTPUT
            self._reset_pin.value = False
            time.sleep(0.1)
            self._reset_pin.value = True
            self._uart.baudrate = self._default_baudrate
            time.sleep(3)  # give it a few seconds to wake up
            self._uart.reset_input_buffer()
            self._initialized = False

    def deep_sleep(self, duration_ms: int) -> bool:
        """Execute deep-sleep command.
        Passing zero as argument will put the chip into deep-sleep forever
        until the RST-pin is pulled low (method hard_reset()).
        This is the typical use-case for an ESP8266 as coprocessor.

        Note that a similar method in the Arduino-libs expects microseconds.
        """
        cmd = "AT+GSLP=" + str(duration_ms)
        try:
            self.at_response(cmd, retries=1)
            return True
        except OKError:
            return False
