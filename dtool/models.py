import asyncio
from time import time, monotonic
from collections import deque
from enum import Enum, StrEnum, IntEnum, auto

class ByteEnum(IntEnum):
    B = 1
    KB = 1024 * B
    MB = 1024 * KB
    GB = 1024 * MB
    TB = 1024 * GB
    PB = 1024 * TB
    EB = 1024 * PB
    ZB = 1024 * EB
    YB = 1024 * ZB


class SpeedInfo:
    __slot__ = ("speed", "time", "process")

    def __init__(self, dprocess, dtime) -> None:
        self.process = dprocess
        self.time = dtime
        if dtime != 0:
            self.speed = dprocess / dtime
        else:
            self.speed = 0


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


class SpeedMonitor:
    def __init__(self, mission, attr_name="process") -> None:
        self._obj = mission
        self._attr_name = attr_name
        self.process_cache = self.process
        self.time = time()

    @property
    def process(self):
        return getattr(self._obj, self._attr_name)

    def __next__(self):
        if self._obj.done.is_set():
            raise StopIteration
        old_process = self.process_cache
        old_time = self.time
        self.process_cache = self.process
        self.time = time()
        return (self.process_cache - old_process) / (self.time - old_time)

    def reset(
        self,
    ):
        self.process_cache = self.process
        self.time = time()

    def info(self) -> tuple:
        t = time()
        return (self.process - self.process_cache) / (t - self.time), (t - self.time)

    async def aget(self, second: int = 1):
        process = self.process
        t = time()
        await asyncio.sleep(second)
        return (self.process - process) / (time() - t)


class BufferSpeedMoniter:
    def __init__(self, mission, buffering, attr_name="process") -> None:
        self._obj = mission
        self._attr_name = attr_name
        self.buffer: deque[tuple] = deque(
            maxlen=buffering
        )  # deque( (time, process), ...)
        self.buffering = buffering

    @property
    def process(self):
        return getattr(self._obj, self._attr_name)

    @staticmethod
    def time():
        return time()

    def reset(self):
        self.buffer = deque(maxlen=self.buffering)
        self.put()

    def put(self):
        self.buffer.append((self.time(), self.process))

    def get(self) -> float:
        time_cache, process_cache = self.buffer[0]
        return (self.process - process_cache) / (self.time() - time_cache)

    def info(self) -> tuple:
        time_cache, process_cache = self.buffer[0]
        return self.time() - time_cache, (self.process - process_cache) / (
            self.time() - time_cache
        )

    def time_passed(self):
        return self.time() - self.buffer[0][0]

    def __next__(self):
        if self._obj.done.is_set():
            raise StopIteration
        time_now = self.time()
        self.buffer.append((time_now, self.process))
        time_cache, process_cache = self.buffer[0]
        if time_cache != time_now:
            return (self.process - process_cache) / (time_now - time_cache)
        else:
            return 0

    def eta(self):
        return self.remain / self.get()


class SpeedCacher:
    def __init__(self, mission, block_num=0, threshold=0.1, accuracy=0.1) -> None:
        self.speed = 0
        self.old_speed = 0
        self.change_num: int = block_num
        self.mission = mission
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


"""
    注意区分: start, process, stop, end, buffer_stop, buffering等

    0 <= start <= stream_process <= stop <= end = file_size
    process + buffering = buffer_stop 
    control_end = min(buffer_stop, stop)
    process <= stop - start

    0:  索引开始的地方
    start:  从这里开始请求资源,如果不允许续传start之前的数据会丢弃
    process:    下载的总字节数
    stream_process: buffer开始处
    stop:   和block.stop相同,是stream函数主动截断的位置
    end:    资源末尾位置,由服务器截断,stop > end会警告
    control_end:    不会在此位置之后创建连接
    buffer_stop:    stream的download函数运行在此会等待

    pre_divition:   在start 和 stop间划分
    re_divition: 根据blocklist在control前划分
    """
