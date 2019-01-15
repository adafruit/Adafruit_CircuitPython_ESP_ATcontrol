"""A 'socket' compatible interface thru the ESP AT command set"""

_the_interface = None
def set_interface(iface):
    global _the_interface
    _the_interface = iface

SOCK_STREAM = const(1)
AF_INET = const(2)

def getaddrinfo(host, port,  # pylint: disable=too-many-arguments
                family=0, socktype=0, proto=0, flags=0): # pylint: disable=unused-argument
    """Given a hostname and a port name, return a 'socket.getaddrinfo'
    compatible list of tuples. Honestly, we ignore anything but host & port"""
    if not isinstance(port, int):
        raise RuntimeError("port must be an integer")
    ipaddr = _the_interface.nslookup(host)
    return [(AF_INET, socktype, proto, '', (ipaddr, port))]

class socket:
    def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None):
        if family != AF_INET:
            raise RuntimeError("Only AF_INET family supported")
        if type != SOCK_STREAM:
            raise RuntimeError("Only SOCK_STREAM type supported")
        self._buffer = b''

    def connect(self, address, conntype=None):
        host, port = address
        if not _the_interface.socket_connect(conntype, host, port, keepalive=10, retries=3):
            raise RuntimeError("Failed to connect to host", host)
        self._buffer = b''

    def write(self, data):
        _the_interface.socket_send(data)

    def readline(self):
        if b'\r\n' not in self._buffer:
            # there's no line already in there, read some more
            self._buffer = self._buffer + _the_interface.socket_receive(timeout=3)
            #print(self._buffer)
        firstline, self._buffer = self._buffer.split(b'\r\n', 1)
        return firstline

    def read(self, num=0):
        if num == 0:
            ret = self._buffer
            self._buffer = b''
        else:
            ret = self._buffer[:num]
            self._buffer = self._buffer[num:]
        return ret

    def close(self):
        _the_interface.socket_disconnect()
