# SPDX-FileCopyrightText: 2019 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_espatcontrol_wifimanager`
================================================================================

WiFi Manager for making ESP32 AT Control as WiFi much easier

* Author(s): Melissa LeBlanc-Williams, ladyada, Jerry Needell
"""

# pylint: disable=no-name-in-module

import adafruit_requests as requests
import adafruit_espatcontrol.adafruit_espatcontrol_socket as socket
from adafruit_espatcontrol.adafruit_espatcontrol import ESP_ATcontrol

try:
    from typing import Dict, Any, Optional, Union, Tuple
    from circuitpython_typing.led import FillBasedLED
except ImportError:
    pass


class ESPAT_WiFiManager:
    """
    A class to help manage the Wifi connection
    """

    def __init__(
        self,
        esp: ESP_ATcontrol,
        secrets: Dict[str, Union[str, int]],
        status_pixel: Optional[FillBasedLED] = None,
        attempts: int = 2,
    ):
        """
        :param ESP_SPIcontrol esp: The ESP object we are using
        :param dict secrets: The WiFi and Adafruit IO secrets dict (See examples)
        :param status_pixel: (Optional) The pixel device - A NeoPixel or DotStar (default=None)
        :type status_pixel: NeoPixel or DotStar
        :param int attempts: (Optional) Unused, only for compatibility for old code
        """
        # Read the settings
        self._esp = esp
        self.debug = False
        self.secrets = secrets
        self.attempts = attempts
        requests.set_socket(socket, esp)
        self.statuspix = status_pixel
        self.pixel_status(0)

    def reset(self) -> None:
        """
        Perform a hard reset on the ESP
        """
        if self.debug:
            print("Resetting ESP")
        self._esp.hard_reset()

    def connect(self, timeout: int = 15, retries: int = 3) -> None:
        """
        Attempt to connect to WiFi using the current settings
        """
        try:
            if self.debug:
                print("Connecting to AP...")
            self.pixel_status((100, 0, 0))
            self._esp.connect(self.secrets, timeout=timeout, retries=retries)
            self.pixel_status((0, 100, 0))
        except (ValueError, RuntimeError) as error:
            print("Failed to connect\n", error)
            raise

    def set_conntype(self, url: str) -> None:
        """set the connection-type according to protocol"""
        self._esp.conntype = (
            ESP_ATcontrol.TYPE_SSL
            if url.startswith("https")
            else ESP_ATcontrol.TYPE_TCP
        )

    def get(self, url: str, **kw: Any) -> requests.Response:
        """
        Pass the Get request to requests and update Status NeoPixel

        :param str url: The URL to retrieve data from
        :param dict data: (Optional) Form data to submit
        :param dict json: (Optional) JSON data to submit. (Data must be None)
        :param dict header: (Optional) Header data to include
        :param bool stream: (Optional) Whether to stream the Response
        :return: The response from the request
        :rtype: Response
        """
        if not self._esp.is_connected:
            self.connect()
        self.pixel_status((0, 0, 100))
        self.set_conntype(url)
        return_val = requests.get(url, **kw)
        self.pixel_status(0)
        return return_val

    def post(self, url: str, **kw: Any) -> requests.Response:
        """
        Pass the Post request to requests and update Status NeoPixel

        :param str url: The URL to post data to
        :param dict data: (Optional) Form data to submit
        :param dict json: (Optional) JSON data to submit. (Data must be None)
        :param dict header: (Optional) Header data to include
        :param bool stream: (Optional) Whether to stream the Response
        :return: The response from the request
        :rtype: Response
        """
        if not self._esp.is_connected:
            self.connect()
        self.pixel_status((0, 0, 100))
        self.set_conntype(url)
        return_val = requests.post(url, **kw)
        return return_val

    def put(self, url: str, **kw: Any) -> requests.Response:
        """
        Pass the put request to requests and update Status NeoPixel

        :param str url: The URL to PUT data to
        :param dict data: (Optional) Form data to submit
        :param dict json: (Optional) JSON data to submit. (Data must be None)
        :param dict header: (Optional) Header data to include
        :param bool stream: (Optional) Whether to stream the Response
        :return: The response from the request
        :rtype: Response
        """
        if not self._esp.is_connected:
            self.connect()
        self.pixel_status((0, 0, 100))
        self.set_conntype(url)
        return_val = requests.put(url, **kw)
        self.pixel_status(0)
        return return_val

    def patch(self, url: str, **kw: Any) -> requests.Response:
        """
        Pass the patch request to requests and update Status NeoPixel

        :param str url: The URL to PUT data to
        :param dict data: (Optional) Form data to submit
        :param dict json: (Optional) JSON data to submit. (Data must be None)
        :param dict header: (Optional) Header data to include
        :param bool stream: (Optional) Whether to stream the Response
        :return: The response from the request
        :rtype: Response
        """
        if not self._esp.is_connected:
            self.connect()
        self.pixel_status((0, 0, 100))
        self.set_conntype(url)
        return_val = requests.patch(url, **kw)
        self.pixel_status(0)
        return return_val

    def delete(self, url: str, **kw: Any) -> requests.Response:
        """
        Pass the delete request to requests and update Status NeoPixel

        :param str url: The URL to PUT data to
        :param dict data: (Optional) Form data to submit
        :param dict json: (Optional) JSON data to submit. (Data must be None)
        :param dict header: (Optional) Header data to include
        :param bool stream: (Optional) Whether to stream the Response
        :return: The response from the request
        :rtype: Response
        """
        if not self._esp.is_connected:
            self.connect()
        self.pixel_status((0, 0, 100))
        self.set_conntype(url)
        return_val = requests.delete(url, **kw)
        self.pixel_status(0)
        return return_val

    def ping(self, host: str, ttl: int = 250) -> Union[int, None]:
        """
        Pass the Ping request to the ESP32, update Status NeoPixel, return response time

        :param str host: The hostname or IP address to ping
        :param int ttl: (Optional) The Time To Live in milliseconds for the packet (default=250)
        :return: The response time in milliseconds
        :rtype: int
        """
        if not self._esp.is_connected:
            self.connect()
        self.pixel_status((0, 0, 100))
        response_time = self._esp.ping(host, ttl=ttl)
        self.pixel_status(0)
        return response_time

    def pixel_status(self, value: Union[int, Tuple[int, int, int]]) -> None:
        """
        Change Status NeoPixel if it was defined

        :param value: The value to set the Board's Status NeoPixel to
        :type value: int or 3-value tuple
        """
        if self.statuspix:
            self.statuspix.fill(value)
