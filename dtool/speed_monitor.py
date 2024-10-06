from collections import deque
from asyncio import sleep
from time import time
from .dtool import DownloadBase


def buffer_monitor(size, mission: DownloadBase):
    info = deque(size)
    while 1:
        process = mission.process
        time_now = time()
        info.append((process, time_now))
        i = info[0]
        yield (process - i[0]) / (time_now - i[1])


async def async_moniter(speed, mission: DownloadBase):
    m = buffer_monitor(speed, mission)
    for speed in m:
        sleep(1 / speed)
        mission.speed = speed
