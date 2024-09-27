import asyncio, httpx, aiofiles
from asyncio import Task
import dtool
import time
from time import time, monotonic
from collections import deque
from enum import IntEnum



class DataUnit(IntEnum):
    B = 1
    KB = 1024


class TimeUnit(IntEnum):
    s = 1
    m = 60
    h = 60 * m
    d = 24 * h


class Inf:
    __slot__ = ()
    def __eq__(self, value: object) -> bool:
        """return self == other"""
        return value is Inf

    def __gt__(self, other):
        """return self > other"""
        return True

    def __lt__(self, other):
        """retrun self < other"""
        return False

    def __gn__(self, other):
        """return self >= other"""
        return self > other or self == other

    def __ln__(self, other):
        """return self <= other"""
        return self < other or self == other

    def __add__(self, other):
        """return self + other"""
        return self

    def __radd__(self, other):
        return self

    def __sub__(self, other):
        """return self - other"""
        return self

    def __rsub__(self, other):
        return self

    def __str__(self) -> str:
        return ""

class CircleTempFile:

    def __init__(self, size) -> None:
        self._size = size
        self._off = 0

    async def __await__(self):
        self._temp_file = await aiofiles.tempfile.TemporaryFile("w+b")

    async def seek(self, off):
        self._off = off % self._size
        await self._temp_file.seek(self._off)
    
    async def write(self, data):
        size = len(data)
        if size > self._size:
            raise ValueError
        if size + self._off < self._size:
            await self._temp_file.write(data)
            self._off += size
        else:
            await self._temp_file.write(data[:self._size - self._off])
            await self._temp_file.seek(0)
            await self._temp_file.write(data[self._size - self._off:])
            self._off += size - self._size

    async def read(self, size):
        if size > self._size:
            raise ValueError
        if size + self._off < self._size:
            self._off += size
            return await self._temp_file.read(size)
        else:
            i = await self._temp_file.read(size - ) + 
            await self._temp_file.seek(0)
            i += await self._temp_file.write(data[self._size - self._off:])
            self._off += size - self._size


class StreamCon:
    def __init__(self) -> None:
        self.block_list = 1
        self._start = 1
        self._end = 1
        self.step = 1
        self.wait_download = asyncio.Event()
        self.wait_iter = asyncio.Event()

    async def download(self, block):
        assert block in self.block_list
        while True:
            len_chunk = len(chunk)
            # wait iter
            while block.process + len_chunk > self.end:
                self.wait_iter.clear()
                await self.wait_iter.wait()

            # write
            yield

            # call iter  暂时没有结束检测
            if (
                block == self.block_list[0]
                and block.process + len_chunk > self.start + self.step
            ):
                self.wait_download.set()

    async def iter(self):
        while True:
            if self.start + self.step > self.block_list[0].process:
                self.wait_download.clear()
                await self.wait_download.wait()

            yield
            self.start += self.step

            # call download
            self.wait_iter.set()


class CircleFuffer:
    def __init__(self, size) -> None:
        self._size = size
        self._off = 0
        self._io = bytearray(size)

    def seek(self, off):
        self._off = off % self._size

    def write(self, data):
        size = len(data)
        if size > self._size:
            raise ValueError
        if size + self._off < self._size:
            self._io[self._off : self._off + size] = data
            self._off += size
        else:
            self._io[self._off :] = data[: self._size - self._off]
            self._io[: self._off + size - self._size] = data[self._size - self._off :]
            self._off += size - self._size

    def read(self, size):
        if size > self._size:
            raise ValueError
        if size + self._off < self._size:
            i = bytes(self._io[self._off : self._off + size])
            self._off += size
            return i
        else:
            i = bytes(self._io[self._off :] + self._io[: self._off + size - self._size])
            return i

    def tell(self):
        return self._io.tell()


class CircleStream:
    def __init__(self, size, block_list: list, step=1024**2) -> None:
        self.size = size
        self.block_list = block_list
        self._start = 0
        self._end = self._start + size
        self.step = step
        self._io = CircleFuffer(size)

        self.wait_download = asyncio.Event()
        self.wait_iter = asyncio.Event()
        self.wait_download.set()
        self.wait_iter.set()

    @property
    def start(self):
        return self._start

    @start.setter
    def start(self, value):
        self._start += value
        self._end += value

    @property
    def end(self):
        return self._end

    async def seek_and_write(self, pos, data):
        if pos + len(data) > self.end:
            self.wait_iter.clear()
            await self.wait_iter.wait()

        self._io.seek(pos)
        self._io.write(data)

        if self.block_list[0].process > self.start + 1024:
            self.wait_download.set()

    async def __anext__(self):
        if self.start + self.step > self.block_list[0].process:
            self.wait_download.clear()
            await self.wait_download.wait()

        self._io.seek(self.start)
        i = self._io.read(self.step)

        self.wait_iter.set()
        self.start += self.step

        return i

    async def __aiter__(self):
        return self


class CricleFile:
    def __init__(self) -> None:
        self._file = aiofiles.tempfile.TemporaryFile("w+b")

    async def __aenter__(self):
        return await self

    async def __await__(self):
        await self._file

    async def __aexit__(self):
        self


class DataChunk:
    __slot__ = ("start", "end", "data")

    def __init__(self, start_pos) -> None:
        self.start = start_pos
        self.end = start_pos

    def __len__(self):
        return self.end - self.start

    def seek(self):
        pass

    def write(self):
        pass



class SpeedMonitor:
    def __init__(self, mission, attr_name="process") -> None:
        self._obj = mission
        self._attr_name = attr_name
        self.process_cache = self.process
        self.time = time.time()

    @property
    def process(self):
        return getattr(self._obj, self._attr_name)

    def __next__(self):
        old_process = self.process_cache
        old_time = self.time
        self.process_cache = self.process
        self.time = time.time()
        return (self.process_cache - old_process) / (self.time - old_time)

    def reset(self,):
        self.process_cache = self.process
        self.time = time.time()

    def get(self):
        time.sleep(1)
        return (self.process - self.process_cache) / (time.time() - self.time)

    def info(self) -> tuple:
        t = time.time()
        return (self.process - self.process_cache) / (t - self.time), (t - self.time)

    async def aget(self, second: int = 1):
        process = self.process
        t = time.time()
        await asyncio.sleep(second)
        return (self.process - process) / (time.time() - t)


class BufferSpeedMoniter:
    def __init__(self, mission, buffering, attr_name = 'process') -> None:
        self._obj = mission
        self._attr_name = attr_name
        self.buffer :deque[tuple[float|int]]= deque(maxlen = buffering)
    @property
    def process(self):
        return getattr(self._obj, self._attr_name)
    
    @staticmethod
    def time():
        return time()
    
    def put(self):
        self.buffer.append((self.time(), self.process))

    def get(self) -> float:
        return self.buffer[0]
    
    def info(self) -> tuple:
        return ()

    def __next__(self):
        time_now = self.time()
        self.buffer.append((time_now, self.process))
        time_cache, process_cache = self.buffer[0]
        return (self.process - process_cache) / (time_now - time_cache)
    
    def eta(self):
        return self.remain / self.get()


class SpeedCacher:
    def __init__(self, mission, block_num=0, threshold=0.1, accuracy=0.1) -> None:
        self.speed = 0
        self.old_speed = 0
        self.change_num: int = block_num
        self.mission: dtool.DownloadIO = mission
        self.monitor = SpeedMonitor(mission)
        self.max_speed_per_thread = 0
        self.threshold = threshold  # 判定阈值 >=0 <1 无量纲
        self.accuracy = accuracy  # 精确度 >=0 单位为秒 越大越精确但响应更慢 防止短时间内速率波动 除于秒数后等价于判定阈值

    def reset(self, block_num):
        self.speed = 0
        self.old_speed = 0
        self.max_speed_per_thread = 0
        self.change_num = block_num

    def change(self, change_num: int = 1):
        if change_num != 0:
            self.monitor.reset()
            self.old_speed = self.speed
            self.change_num = change_num

    def new_connect(self):
        if self.check:
            self.mission.re_divition_task()
            self.change()

    def get_speed(self):
        self.speed = next(self.monitor)
        return (self.speed - self.old_speed) / self.change_num

    def get(self):  # old
        self.speed = next(self.monitor)
        if (i := self.speed / self.mission.task_num) > self.max_speed_per_thread:
            self.max_speed_per_thread = i
        return (
            (self.speed - self.old_speed) / self.change_num / self.max_speed_per_thread
        )

    def check(self) -> bool:  # new
        self.speed, secend = self.monitor.info()
        if (i := self.speed / self.mission.task_num) > self.max_speed_per_thread:
            self.max_speed_per_thread = i
        if secend > 60:
            self.monitor.reset()
        return (
            (self.speed - self.old_speed) / self.change_num / self.max_speed_per_thread
            - self.threshold
        ) > self.accuracy / secend


class bytearrayIO:
    def __init__(self) -> None:
        self.data = bytearray()
        self.off = 0
        self.len_data = 0

    def seek(self, off):
        if off > self.len_data:
            self.data.extend(b"\x00" * (off - self.len_data))
            self.len_data = off
        self.off = off

    def write(self, data: bytes):
        self.data[self.off : self.off + len(data)] = data
        self.off += len(data)

    def read(self, size):
        i = self.data[self.off : self.off + size]
        self.off += size

    def read_all(self):
        return self.data


class LoopTimer:

    def __init__(self) -> None:
        self.on_stop_time = 0
        self.stop_time = time.time()
    def start(self):
        self.on_stop_time += time.time() - self.stop_time
    def stop(self):
        self.stop_time = time.time()
    def time(self):
        return time.time() - self.on_stop_time