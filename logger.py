import logging
logging.basicConfig(level=logging.DEBUG)

import duw as DUW

def archive(dev, reg, val=-1):
    # log a bus transaction, val may not be set for read requests (when reg is
    # an odd number)
    with DUW.session_scope() as S:
        S.add(DUW.RegisterValue(dev=dev, reg=reg, val=val))

listener = DUW.BusListener()
listener.add_listener(archive)
listener.listen()
