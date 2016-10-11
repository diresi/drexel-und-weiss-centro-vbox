import datetime
from collections import defaultdict

from . import scoped_session, RegisterValue

DEV_ID_REG = 5000

class BaseHandler(object):
    def __init__(self, bus=None):
        self.bus = bus
        if self.bus:
            self.bus.add_listener(self.inject)

    def inject(self, dev, reg, val=-1):
        pass

class DeviceCache(object):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.devices = defaultdict(dict)

    def inject(self, dev, reg, val=-1):
        cache = self.devices[dev]
        cache[reg] = (val, datetime.datetime.utcnow())
        if not cache.get(DEV_ID_REG, None) and self.bus:
            # trigger a read request for this device type
            # we can't be sure that this request is actually heard, but
            # eventually it will cause the device to report its device type
            # (stored in register 5000)
            # this type can be used to look up the correct specification csv.
            self.bus.read_request(dev, DEV_ID_REG)

class DeviceArchive(BaseHandler):
    def inject(self, dev, reg, val=-1):
        # log a bus transaction, val may not be set for read requests (when reg is
        # an odd number)
        with scoped_session() as S:
            S.add(RegisterValue(dev=dev, reg=reg, val=val))
