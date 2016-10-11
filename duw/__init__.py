from .db import scoped_session, RegisterValue
from .bus import Bus, BusListener
from .device import DeviceCache, DeviceArchive
from .logger import Logger

def default_logging():
    import logging
    logging.basicConfig(filename="duw.log", style="{", level=logging.DEBUG)

def interactive_setup():
    default_logging()
    global logger
    logger = Logger()
    logger.start()
    return logger
