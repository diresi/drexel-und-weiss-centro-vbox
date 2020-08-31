from threading import Thread
from . import BusListener, DeviceCache, DeviceArchive

class Logger(object):
    def __init__(self):
        self.bus = BusListener()
        self.cache = DeviceCache(self.bus)
        self.archive = DeviceArchive(self.bus)
        self.thread = Thread(daemon=True, target=self.bus.listen)

    def replay(self):
        self.archive.replay()

    def start(self):
        self.thread.start()
        return self.thread
