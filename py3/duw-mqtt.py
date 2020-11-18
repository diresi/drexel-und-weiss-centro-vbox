import asyncio
import csv
import json
import logging
import random
import time

from aioserial import AioSerial
from asyncio_mqtt import Client as MqttClient, MqttError

_log = logging.getLogger(__name__)

SER_PORT = "/dev/ttyUSB0"
SER_BAUD = 115200
SER_TMO = 1

MQTT_BROKER = "192.168.1.11"
MQTT_TOPIC_TELE = "tele/aerosmart/bus"
MQTT_TOPIC_TELE_VALUE = "tele/aerosmart/{device}/{name}"
MQTT_TOPIC_CMND = "cmnd/aerosmart/bus"

# ranges of device addresses we're interested in
DEVICE_TYPES = {}
DEVICES = {}


class _Feedback:
    def __init__(self):
        self._what = None
        self._seen = False

    def wait_for(self, what):
        self._what = what
        self._seen = False

    def put(self, what):
        if what == self._what:
            self._seen = True

    def seen(self):
        return self._seen


_loopback = _Feedback()


async def read_bus(ser: AioSerial, q: asyncio.Queue):
    while True:
        data = await ser.readline_async()
        _log.debug(f"Bus read: {data}")
        data = bytes(filter(None, data))  # strip null bytes
        data = data.strip().decode()
        if not data:
            continue
        _loopback.put(data)
        await q.put(data)


async def publish_data(mq: MqttClient, q: asyncio.Queue):
    while True:
        data = await q.get()

        msg = parse_bus_msg(data)
        if not msg:
            continue

        msg = process_bus_msg(msg)
        if not msg:
            continue

        await mq_publish(mq, MQTT_TOPIC_TELE, msg)
        if "name" in msg:
            topic = MQTT_TOPIC_TELE_VALUE.format(**msg)
            await mq_publish(mq, topic, msg["value"])


async def mq_publish(mq, topic, msg):
    _log.debug(f"MQTT publish [{topic}]: {msg}")
    msg = json.dumps(msg)
    await mq.publish(topic, msg, qos=1)


def parse_bus_msg(data):
    msg = {"raw": data}
    parts = data.split()
    if len(parts) > 0:
        try:
            msg["device"] = int(parts[0])
        except ValueError:
            pass
    if len(parts) > 1:
        try:
            msg["register"] = int(parts[1])
        except ValueError:
            pass
    if len(parts) > 2:
        try:
            msg["value"] = int(parts[2])
        except ValueError:
            pass
    return msg


def process_bus_msg(msg):
    dev = msg.get("device")
    if not dev:
        return msg

    dev = DEVICES.get(dev)
    if dev is None:
        return None

    reg = msg.get("register")
    if reg % 2:
        # this is the response to a read-request (has the LSB set as flag)
        # just drop the flag
        msg["_register"] = reg
        reg = reg - 1
        msg["register"] = reg
        msg["hint"] = "response to read request"

    val = msg.get("value")
    if val is None:
        return msg

    dev.cache[reg] = val

    spec = dev.regs.get(reg)
    if spec:
        msg["_value"] = val
        msg["value"] = compute_register_value(spec, val)
        msg["name"] = spec.name
    return msg


def compute_register_value(spec, val):
    return val / spec.divisor / (10 ** spec.comma)


async def mqtt_listen(mq: MqttClient, q: asyncio.Queue, topic=MQTT_TOPIC_CMND):
    await mq.subscribe(topic)

    async with mq.filtered_messages(topic) as messages:
        async for message in messages:
            topic = message.topic
            data = message.payload.decode()
            _log.debug(f"MQTT incoming [{topic}]: {data}")

            msg = parse_mqtt_msg(topic, data)
            if not msg:
                continue

            try:
                cmnd = process_mqtt_msg(topic, msg)
            except Exception:
                cmnd = None
                _log.exception(f"while processing message [{topic}]: {msg}")
            if not cmnd:
                continue

            await q.put(cmnd)


async def write_to_ser(ser: AioSerial, q: asyncio.Queue):
    while True:
        cmnd = await q.get()
        await write_cmnd(ser, cmnd)


async def write_cmnd(ser, cmnd, tmo=SER_TMO):
    _log.debug(f"Bus write {cmnd}")
    enc = (cmnd + "\r\n").encode("ascii")

    _loopback.wait_for(cmnd)
    tst = time.time() + tmo
    i = 0
    while True:
        i += 1
        await ser.write_async(enc)
        if _loopback.seen():
            break

        if time.time() > tst:
            _log.warning(
                f"Bus write failed after {i} attempts, timeout reached: {tmo}s"
            )
            break

        await asyncio.sleep(0.1 * random.random())


def parse_mqtt_msg(topic, msg):
    try:
        return json.loads(msg)
    except json.JSONDecodeError:
        pass
    return None


def process_mqtt_msg(topic, msg):
    dev = msg.get("device")
    reg = msg.get("register")
    if not all((dev, reg)):
        return None

    val = msg.get("value")
    if val is None:
        # this is a read request, it needs to have the LSB set
        cmnd = read_reg_cmnd(dev, reg)

    else:
        # this is a write request
        cmnd = "{dev:d} {reg:d} {val:d}".format(dev=dev, reg=reg, val=val)
    return cmnd


def load_device(fn):
    lines = open(fn).readlines()
    dialect = csv.Sniffer().sniff(lines[0])
    rows = csv.reader(lines, dialect)
    regs = {}
    for row in rows:
        try:
            reg = Register(
                int(row[0]),
                row[1],
                int(row[2]),
                int(row[3]),
                int(row[4]),
                int(row[5]),
                row[6],
                row[7],
            )
            regs[reg.addr] = reg
        except ValueError:
            _log.error(f"failed to parse row {row}")
    return regs


class Register:
    def __init__(self, addr, name, vmin, vmax, divisor, comma, access, pcb):
        self.addr = addr
        # we're using the name as mqtt topic, we don't wanna have slashes there
        self.name = name.replace("/", "-")
        self.vmin = vmin
        self.vmax = vmax
        self.divisor = divisor
        self.comma = comma
        self.access = access
        self.pcb = pcb


class Device:
    def __init__(self, addr, type_=None):
        self.addr = addr
        self.cache = {}
        self.regs = {}
        if type_:
            self.cache[5000] = type_
            self.regs = DEVICE_TYPES[type_]

    def type(self):
        return self.cache.get(5000)


def read_reg_cmnd(dev, reg):
    if not reg % 2:
        reg = reg + 1
    return "{dev:d} {reg:d}".format(dev=dev, reg=reg)


async def poll_devices(q: asyncio.Queue):
    # poll some temperatures
    cmnds = [
        read_reg_cmnd(9130, 200),
        read_reg_cmnd(9130, 202),
        read_reg_cmnd(9130, 250),
    ]
    while True:
        # for addr, dev in DEVICES.items():
        #     if dev.type() is None:
        #         await write_cmnd(read_reg_cmnd(dev, 5000))

        for cmnd in cmnds:
            await q.put(cmnd)

        await asyncio.sleep(60 * 10)


async def main():
    # map device type (read from register 5000) -> register description
    # dev type 12 -> vbox 120
    DEVICE_TYPES[12] = load_device("vbox120.csv")
    # dev type 16 -> centro
    DEVICE_TYPES[16] = load_device("centro.csv")

    # pre-configure well-known devices
    for dev in (
        Device(9120, 16),
        Device(9130, 16),
        Device(9150, 12),
    ):
        DEVICES[dev.addr] = dev

    tasks = set()

    async with MqttClient(MQTT_BROKER) as mq:

        qin = asyncio.Queue()
        tasks.add(asyncio.create_task(publish_data(mq, qin)))

        ser = AioSerial(port=SER_PORT, baudrate=SER_BAUD)
        tasks.add(asyncio.create_task(read_bus(ser, qin)))

        qout = asyncio.Queue()
        tasks.add(asyncio.create_task(write_to_ser(ser, qout)))
        tasks.add(asyncio.create_task(poll_devices(qout)))
        tasks.add(asyncio.create_task(mqtt_listen(mq, qout)))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
