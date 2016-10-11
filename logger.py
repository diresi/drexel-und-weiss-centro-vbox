import logging
logging.basicConfig(level=logging.DEBUG)

import duw as DUW

bus = DUW.BusListener()
cache = DUW.DeviceCache(bus)
archive = DUW.DeviceArchive(bus)
archive.replay()
bus.listen()
