#from .dtool import DownloadBase
import asyncio
import weakref
from abc import ABC, abstractmethod
from typing import Iterable
from time import time
from collections import deque
class MonitorBase(ABC):
    @abstractmethod
    async def update(self, size):
        raise NotImplementedError


class Speedlimit(MonitorBase):
    def __init__(self, limit = 0):
        self.limit = limit
        self.last_time = time()

    async def update(self, size):
        if self.limit != 0:
            t = time()
            d_time = t - self.last_time #注意d_time 可能小于0
            if d_time * self.limit < size:
                sleep_time = size / self.limit - d_time
                self.last_time = t + sleep_time#请勿将此行放在await后，会造成数据竞争
                await asyncio.sleep(sleep_time)
            else:
                self.last_time = t


class BufferMonitor(MonitorBase):
    def __init__(self, buffering = 10):
        self.speed_cache = deque(maxlen=buffering)
        self.downloaded_bytes = 0
    
    async def update(self, size):
        self.downloaded_bytes += size
        self.speed_cache.append((time(), self.downloaded_bytes))
    
    @property
    def speed(self):
        if len(self.speed_cache) > 2:
            t, b = self.speed_cache[-1]
            t0, b0 = self.speed_cache[0]
            return (b - b0) / (t - t0)
        else:
            return 0

class BufferLimit(MonitorBase):
    def __init__(self, limit, buffering = 10):
        self.limit = limit
        self.size_sum = 0

    async def update(self, size):
        if self.limit != 0:
            t = time()
            d_time = t - self.last_time #注意d_time 可能小于0
            if d_time * self.limit < size:
                sleep_time = size / self.limit - d_time
                self.last_time = t + sleep_time#请勿将此行放在await后，会造成数据竞争
                await asyncio.sleep(sleep_time)
            else:
                self.last_time = t


class Monitor:
    def __init__(self,*,groups:set[Speedlimit]|None = None, limit:int|None = None):
        if groups is not None:
            self._groups = groups
        else:
            self._groups = set()
        if limit is not None:
            self._groups.add(Speedlimit(limit))
        
        
    async def update(self, size):
        for group in self._groups:
            await group.update(size)

    def add_group(self, group):
        self._groups.add(group)

    def new_group(self, limit):
        g = Speedlimit(limit)
        self._groups.add(g)
        return g