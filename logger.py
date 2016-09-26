import logging
logging.basicConfig(level=logging.DEBUG)

import duw as DUW

bus = DUW.BusListener()
bus.add_listener(archive)
cache = DUW.DeviceCache(bus)
archive = DUW.DeviceArchive(bus)
bus.listen()
