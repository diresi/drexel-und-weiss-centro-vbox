import asyncio
import json
import logging

from aioserial import AioSerial
from asyncio_mqtt import Client as MqttClient, MqttError

_log = logging.getLogger(__name__)

SERPORT = "/dev/ttyUSB0"
SERBAUD = 115200

MQTT_BROKER = "192.168.1.11"
MQTT_TOPIC_TELE = "tele/aerosmart/bus"
MQTT_TOPIC_CMND = "cmnd/aerosmart/bus"

# ranges of device addresses we're interested in
DEVICES = (range(9000, 10000),)


async def read_bus(ser: AioSerial, q: asyncio.Queue):
    while True:
        data = await ser.readline_async()
        _log.debug(f"Bus read: {data}")
        data = bytes(filter(None, data))  # strip null bytes
        data = data.strip().decode()
        if not data:
            continue
        await q.put(data)


async def publish_data(mq: MqttClient, q: asyncio.Queue, topic=MQTT_TOPIC_TELE):
    while True:
        data = await q.get()

        msg = parse_bus_msg(data)
        if not msg:
            continue

        msg = process_bus_msg(msg)
        if not msg:
            continue

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

    for addrs in DEVICES:
        if dev in addrs:
            break
    else:
        return None

    reg = msg.get("register")
    if reg % 2:
        # this is the response to a read-request (has the LSB set as flag)
        # just drop the flag
        msg["_register"] = reg
        msg["register"] = reg - 1
        msg["hint"] = "response to read request"

    # FIXME: implement value correction based on the register specification
    # (see
    # https://github.com/diresi/drexel-und-weiss/blob/master/900.6667_00_TI_Modbus_Parameter_V4.01_DE.pdf)

    return msg


async def mqtt_listen(mq: MqttClient, ser: AioSerial, topic=MQTT_TOPIC_CMND):
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

            cmnd = (cmnd + "\r\n").encode("ascii")
            _log.debug(f"Bus write {cmnd}")

            await ser.write_async(cmnd)


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
        if not reg % 2:
            reg = reg + 1
        cmnd = "{dev:d} {reg:d}".format(dev=dev, reg=reg)

    else:
        # this is a write request
        cmnd = "{dev:d} {reg:d} {val:d}".format(dev=dev, reg=reg, val=val)
    return cmnd


async def main():
    tasks = set()

    async with MqttClient(MQTT_BROKER) as mq:

        q = asyncio.Queue()
        tasks.add(asyncio.create_task(publish_data(mq, q)))

        ser = AioSerial(port=SERPORT, baudrate=SERBAUD)
        tasks.add(asyncio.create_task(read_bus(ser, q)))

        tasks.add(asyncio.create_task(mqtt_listen(mq, ser)))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
