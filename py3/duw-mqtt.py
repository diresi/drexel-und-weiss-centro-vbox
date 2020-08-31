import asyncio
import json
import logging

from aioserial import AioSerial
from asyncio_mqtt import Client as MqttClient, MqttError

_log = logging.getLogger(__name__)

SERPORT = "/dev/ttyUSB0"
SERBAUD = 115200

MQTT_BROKER = "192.168.1.11"
MQTT_TOPIC = "tele/aerosmart/data"

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


async def publish_data(mq: MqttClient, q: asyncio.Queue):
    topic = MQTT_TOPIC
    while True:
        data = await q.get()
        msg = mk_msg(data)
        if not msg:
            continue
        _log.debug(f"MQTT publish [{topic}]: {msg}")
        await mq.publish(MQTT_TOPIC, msg, qos=1)


def mk_msg(data):
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
    msg = process_msg(msg)
    if not msg:
        return None
    return json.dumps(msg)


def process_msg(msg):
    dev = msg.get("device")
    if not dev:
        return msg

    for addrs in DEVICES:
        if dev in addrs:
            break
    else:
        return None

    return msg


async def main():
    tasks = set()

    async with MqttClient(MQTT_BROKER) as mq:

        q = asyncio.Queue()
        tasks.add(asyncio.create_task(publish_data(mq, q)))

        ser = AioSerial(port=SERPORT, baudrate=SERBAUD)
        tasks.add(asyncio.create_task(read_bus(ser, q)))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
