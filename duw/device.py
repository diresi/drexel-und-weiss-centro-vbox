import datetime
import threading
from contextlib import contextmanager
from collections import defaultdict

from . import scoped_session, RegisterValue

utcnow = datetime.datetime.utcnow
DEV_ID_REG = 5000

# kann mir jemand mit dem d&w excel tool evtl. sagen was das register:5344
# bedeutet? dieses taucht in der modbusdoku nirgends auf wird aber alle 10min mit
# dem Wert:130 rausgeschrieben. Ich denke es wird irgendein status sein??
#
# das ist die E_CENTRO_ID (legt Zugehörigkeit von der vbox zum centro fest). Du
# hast zwar weder eine vbox noch eine centro (vermute ich), aber die Platinen
# sind überall identisch. Das ist eine Art regelmäßiges "Announcement" (oder
# nenne es "Ping") hat vermutlich für dich keine Bedeutung.

class BaseHandler(object):
    def __init__(self, bus=None, active=True):
        self._active = threading.Event()
        if active:
            self._active.set()

        self.bus = bus
        if self.bus:
            self.bus.add_listener(self._inject)

    @property
    def active(self):
        return self._active.is_set()

    @active.setter
    def active(self, enable=True):
        if enable:
            self._active.set()
        else:
            self._active.clear()

    @contextmanager
    def scoped_active(self, enable=True):
        current = self.active
        self.active = enable
        yield
        self.active = current

    def _inject(self, *a, **kw):
        if self.active:
            return self.inject(*a, **kw)

class DeviceCache(BaseHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.devices = defaultdict(dict)

    def inject(self, dev, reg, val=-1):
        cache = self.devices[dev]
        cache[reg] = (val, utcnow())

        # actively poll some values of interest
        v = cache.get(DEV_ID_REG, None)
        if not v or (v[0] is None and (utcnow() - v[1]) > datetime.timedelta(seconds=10)):
            # make sure we're not notorious 'bout this request
            cache[DEV_ID_REG] = (None, utcnow())

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

    def replay(self, rvs=None):
        if rvs is None:
            rvs = RegisterValue.query.all()

        # replay bus events, but disable my own listener ;)
        with self.scoped_active(False):
            for rv in rvs:
                self.bus._dispatch(rv.dev, rv.reg, rv.val)

