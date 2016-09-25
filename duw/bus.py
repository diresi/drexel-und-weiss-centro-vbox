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
#   <D&W Device ID><Space><RegisterID><Space><Value><CR><LF>

import serial
import logging
slog = logging.getLogger(__name__)

xCR = "\r".encode()[0]
xNL = "\n".encode()[0]

class Bus(object):
    def __init__(self, tty=None):
        if tty is None:
            tty = "/dev/ttyUSB0"
        self._port = serial.Serial(tty, 115200, timeout=5)

    def _send(self, s):
        self._port.write((s+"\r\n").encode("ascii"))

    def read_request(self, dev, reg):
        #self.port.reset_output_buffer()
        self._send("{dev:d} {reg:d}".format(dev=dev, reg=reg+1))

    def write_request(self, dev, reg, val):
        #self.port.reset_output_buffer()
        self._send("{dev:d} {reg:d} {val:d}".format(dev=dev, reg=reg, val=val))

    def _read_line(self):
        # this reads a line terminated with \n. pretty much the same as
        # serial.threaded.LineReader.
        b = bytearray()
        while b[-1] != xNL:
            b.extend(self._port.read())
        return b.decode().strip().split()

    def watch(self, handler):
        parts = self._read_line()
        slog.debug("Bus read: {!r}".format(parts))
        parts = [int(part) for part in parts]
        handler(*parts)
