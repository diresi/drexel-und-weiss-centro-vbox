# DuW debug bus access, inspired by https://github.com/smarthomeNG/smarthome
# (thanks guys), but their implementation really sucks (sorry, but it's true).

# from smarthome.py and
# https://knx-user-forum.de/forum/öffentlicher-bereich/knx-eib-forum/23921-wärmepumpe-wohnraumlüftung-drexel-und-weiss?p=558811#post558811
#
# Write (ASCII plain text):
#   <D&W Device ID><Space><RegisterID><Space><Value><CR><LF>
# Response (ASCII plain text):
#   <D&W Device ID><Space><RegisterID><Space><Value><CR><LF>
#
# Read (ASCII plain text):
#   <D&W Device ID><Space><RegisterID+1><CR><LF>
# Response (ASCII plain text):
#   <D&W Device ID><Space><RegisterID+1><Space><Value><CR><LF>

from threading import Event, Lock
import logging
slog = logging.getLogger(__name__)
import warnings

import serial

xCR = "\r".encode()[0]
xNL = "\n".encode()[0]

class Bus(object):
    def __init__(self, tty=None):
        if tty is None:
            tty = "/dev/ttyUSB0"
        self._lock = Lock()
        try:
            self._port = serial.Serial(tty, 115200, timeout=5)
        except Exception as e:
            self._port = None
            slog.warning("failed to open serial device: {}".format(tty))
        self._terminate = Event()

    def terminate(self):
        self._terminate.set()

    def should_terminate(self):
        return self._terminate.is_set()

    def _send(self, s):
        if not self._port:
            warnings.warn("ignoring _send request, no serial device available")
            return
        with self._lock:
            self._port.write((s+"\r\n").encode("ascii"))

    def read_request(self, dev, reg):
        #self.port.reset_output_buffer()
        req = "{dev:d} {reg:d}".format(dev=dev, reg=reg+1)
        slog.debug("Bus write: {!r}".format(req))
        self._send(req)

    def write_request(self, dev, reg, val):
        #self.port.reset_output_buffer()
        self._send("{dev:d} {reg:d} {val:d}".format(dev=dev, reg=reg, val=val))

    def _read_line(self):
        # this reads a line terminated with \n. pretty much the same as
        # serial.threaded.LineReader.
        b = bytearray()
        while not self.should_terminate():
            # skip zero bytes
            b.extend(filter(None, self._port.read()))
            if b and b[-1] == xNL:
                break
        parts = b.decode().strip().split()
        slog.debug("Bus read: {!r}".format(parts))
        return parts

class BusListener(Bus):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._listeners = []

    def add_listener(self, l):
        if l not in self._listeners:
            self._listeners.append(l)

    def _dispatch(self, *parts):
        if not self.should_terminate():
            for l in self._listeners:
                l(*parts)

    def listen(self):
        while not self.should_terminate():
            parts = self._read_line()
            parts = [int(part) for part in parts]

            if len(parts) == 3 and parts[1] % 2:
                # response to explicit read request (uses reg+1, device responds
                # with this reg+1), we're normalizing the register value
                parts[1] -= 1

            self._dispatch(*parts)
