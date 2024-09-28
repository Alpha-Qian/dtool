import asyncio, httpx, aiofiles
from asyncio import Event, Lock
from collections import deque
from abc import ABC, abstractmethod
from pathlib import Path

from .models import Inf, CircleFuffer, SpeedMonitor, BufferSpeedMoniter, SpeedInfo
from .taskcoordinator import TaskCoordinator
from ._config import Config, DEFAULTCONFIG, SECREAT
from ._exception import NotAcceptRangError, NotSatisRangeError
import time

B = 1
KB = 1024
MB = 1048576
GB = 1073741824
TB = 1099511627776


class Block:
    __slots__ = ('process','stop','running')
    def __init__(self, process:int, end_pos:int|Inf = Inf(), running:bool = True) -> None:
        self.process = process
        self.stop = end_pos
        self.running = False#running

    def __str__(self) -> str:
        return f'{self.process}-{self.stop}'

    def __getstate__(self):
        return (self.process, self.stop)
    
    def __setstate__(self, state:tuple):
        self.process, self.stop = state
        # 恢复未序列化的属性
        self.running = False

class PoolBase:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(limits=httpx.Limits())
        self.url = url
        self.block_list:list[Block] = []

        self.inited = False
        self.init_prepare = TaskCoordinator()
        self._headers = None
        self._accept_range = None

        self.alive = Event()
        self.alive.set()
        self.done = Event()

    def divition_task(self,  start_pos:int, ):#end_pos:int|None = None):
        '''自动根据开始位置创建新任务,底层API'''
        if len(self.block_list) > 0 and start_pos < self.block_list[-1].stop:
            match = False
            for block in self.block_list:
                if block.process < start_pos < block.stop:
                    match = True
                    task_block = Block(start_pos, block.stop, True) #分割
                    block.stop = start_pos
                    self.block_list.insert(self.block_list.index(block)+1,task_block)
                    break
            if not match:
                raise Exception('重复下载')
        else:
            task_block = Block(start_pos, self._file_size, True)
            self.block_list.append(task_block)
        self.task_group.create_task(self.download(task_block))

    def pause(self):
        self.alive.clear()
    
    def resum(self):
        self.alive.set()
    def start(self):
        pass
    def restart(self):
        pass

    async def aclose(self):
        await self.client.aclose()
        await self.task_group.__aexit__()

    def handing_info(self, res):
        pass


class DownloadBase:
    ''''
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
    '''

    def __init__(self, url, start:int = 0, stop:int|Inf = Inf(),/) -> None:
        self.client = httpx.AsyncClient(limits=httpx.Limits())
        self.url = url
        self.block_list:list[Block] = []
        
        self._start = start
        self._stop = stop
        self._process = start
        self._file_size = Inf()

        self.inited = False
        self.init_prepare = TaskCoordinator()
        self._headers = None
        self._accept_range = None

        self._task_num = 0
        self.resume = Event()
        self.resume.set()
        self.done = Event()


    @property
    def start_pos(self):
        return self._start
    
    @property
    def stop_pos(self):
        return self._stop

    @property
    def process(self):
        return self._process
    
    @property
    def file_size(self):
        return self._file_size
    
    @property
    def accept_range(self):
        return self._accept_range
    
    @property
    def task_num(self):
        return len(self.task_group._tasks)

    def pause(self):
        self.resume.clear()
    
    def unpause(self):
        self.resume.set()
    
    def speed_monitor(self):
        process = self._process
        t = time.time()
        while not self.done.is_set():
            yield SpeedInfo(self._process - process, time.time() - t)
            process = self._process
            t = time.time()
        
    def buffer_monitor(self, size = 10):
        info = deque(size + 1)
        while not self.done.is_set():
            process = self.process
            time_now = time.time()
            info.append((process, time_now))
            i = info[0]
            yield SpeedInfo(process - i[0], time_now - i[1])

    async def Daemon_coro(self, sleep_time = 0):
        '''main coro'''
        self.divition_task(self._start)
        async with asyncio.TaskGroup() as self.task_group:
            self.pre_divition(1)
        self.done.set()


    def speed_limet(self, max_speed):
        '''短暂暂停以降低到速度限制'''
        for i in self.buffer_monitor():
            yield
            speed = i.speed
            t = i.time
            if speed > max_speed:
                sleep_time = (speed / max_speed - 1) * t
                self.pause()
                asyncio.get_running_loop().call_later(sleep_time, self.unpause)
    
    @property
    def control_end(self):#兼容层，便于子类在不修改pre_divition,re_divition的情况下修改
        return self._stop
    
    async def start(self):
        if self._entered:
            return
        self._entered = True
        self.task_group = await asyncio.TaskGroup().__aenter__()
        self.divition_task(self._start)
        async with self.init_prepare as res:
            self._handing_info(res)
            self.pre_divition(16)
        return self.done

    async def run(self):
        await self.start()
        await self.task_group.__aexit__()
        await self.done.wait()

    def close(self):
        '''断开所有连接'''
        for task in self.task_group._tasks:
            task.cancel()

    def reset(self):
        self.block_list = []
        self.close()

    def pre_divition(self,  block_num):
        if self._start > self.control_end:
            raise RuntimeError
        block_size = ( self.control_end - self._start ) // block_num
        if block_num != 0:
            for i in range(self._start + block_size, self.control_end - block_num, block_size):
                self.divition_task(i)

    async def re_divition(self) -> bool:
        '''自动在已有的任务中创建一个新连接,成功则返回True'''
        if len(self.block_list) == 0:
            return False
        max_remain = 0
        for block in self.block_list:
            if block.process > self.control_end:
                break

            if block.running:
                if (block.stop - block.process) // 2 > max_remain:
                    max_remain = (min(block.stop, self.control_end) - block.process)//2
                    max_block = block
                    
            else:
                if block.stop - block.process > max_remain:
                    if block.process < self.control_end:
                        max_remain = block.stop - block.process
                        max_block = block
            
        if max_block.running:
            #构建新块
            if max_remain >= self:
                self.divition_task((max_block.process + max_block.stop)//2)
                return True
            return False
        else:
            #启动已有分块
            self.task_group.create_task(self.download(block))
            return True
        
    def divition_task(self,  start_pos:int, ):#end_pos:int|None = None):
        '''自动根据开始位置创建新任务,底层API'''
        if len(self.block_list) > 0 and start_pos < self.block_list[-1].stop:
            match = False
            for block in self.block_list:
                if block.process < start_pos < block.stop:
                    match = True
                    task_block = Block(start_pos, block.stop, True) #分割
                    block.stop = start_pos
                    self.block_list.insert(self.block_list.index(block)+1,task_block)
                    break
            if not match:
                raise Exception('重复下载')
        else:
            task_block = Block(start_pos, self._file_size, True)
            self.block_list.append(task_block)
        self.task_group.create_task(self.download(task_block))

    def _handing_info(self, res:httpx.Response):
        self.inited = True
        self.task_group = await asyncio.TaskGroup().__aenter__()
        self._headers = res.headers
        self._accept_range = 'accept-ranges' in res.headers and res.headers['accept-ranges'] == 'bytes' or res.status_code == httpx.codes.PARTIAL_CONTENT
        if 'content-range' in res.headers and (size := res.headers['content-range'].split('/')[-1]) != '*' :
            #标准长度获取
            self._file_size = int(size)
        elif 'content-length' in res.headers and ( 'content-encoding' not in res.headers or res.headers['content-encoding'] == 'identity' ):
            res.iter_bytes
            #仅适用于无压缩数据，http2可能不返回此报头
            self._file_size = int(res.headers['content-length'])
        else:
            self._file_size = Inf()
            self._accept_range = False
            if self._accept_range:
                #允许续传，但无法获得文件长度，所以发送res的请求时headers应添加range: bytes=0-不然服务器不会返回'content-range'
                self._accept_range = False
                raise RuntimeWarning()
        
        if not self._accept_range and self.req_range.force == SECREAT:
            raise NotAcceptRangError
        self._stop = min(self._stop, self._file_size)
        self.block_list[-1].stop = self._stop
        self.file_name = str(res.url).split('/')[-1]
        
    async def stream(self, block:Block):
        '''基础网络获取生成器,会修改block处理截断和网络错误'''
        await self.resume.wait()
        headers = {"Range": f"bytes={block.process}-"}
        async with client.stream('GET',self.url,headers = headers) as response:
            if response.status_code == 416:
                raise NotSatisRangeError
            response.raise_for_status()
            if not self.inited:
                await self.init_prepare.unlock(response)
            async for chunk in response.aiter_raw():
                len_chunk = len(chunk)
                if block.process + len_chunk < block.stop:
                    yield chunk
                    self._process += len_chunk
                    block.process += len_chunk
                else:
                    yield chunk[: block.stop - block.process]
                    self._process += block.stop - block.process
                    block.process = block.stop
                    break
                await self.resume.wait()

    @abstractmethod   
    async def download(self, block:Block):
        if block.running:
            return
        block.running = True
        self._task_num += 1
        try:
            self.stream(block)
        except httpx.TimeoutException:
            await self.re_divition
            
        else:
            self.block_list.remove(block)
            if len(self.block_list) == 0:
                self.done.set()
        finally:
            self._task_num -= 1
            block.running = False


class StreamBase(DownloadBase):
    '''重写__init__, __aiter__, __aenter__, __aexit__的行为'''
    def __init__(self, *arg, step) -> None:
        super().__init__(*arg)
        self.iter_now = Event()
        self.iter_now.set()
        self._iter_process = self._start
        self._iter_step = step
    
        
    @property
    def iter_process(self):
        return self._iter_process
    
    @iter_process.setter
    def iter_process(self, value):
        self._iter_process = value
        self._buffer_end = self._iter_process + self._buffering
    
    def __aiter__(self):
        return self
    
    async def stream(self, block: Block):
        async for chunk in super().stream(block):
            yield chunk
            if not self.iter_now.is_set() and block == self.block_list[0]:
                self.iter_now.set()
        if len(self.block_list) == 1:
            self.iter_now.set()

    async def __anext__(self):
        if self.iter_process >= self._stop:
            raise StopAsyncIteration
        if len(self.block_list) != 0 and self.iter_process + self._iter_step > self.block_list[0].process:
            self.iter_now.clear()
            await self.iter_now.wait()
        while 

    async def __aenter__(self):
        self.task_group = await asyncio.TaskGroup().__aenter__()
        self.divition_task(0)
        async with self.init_prepare as res:
            self._handing_info(res)
            self.block_list[-1].stop = self._file_size
        return self
    
    async def __aexit__(self, et, exv, tb):
        assert self._entered
        for i in self.task_group._tasks:
            i.cancel()
        await self.task_group.__aexit__()
        self._buffer = None
        return False
    

    def re_divition(self) -> bool:
        pass




class BufferBase(StreamBase):

    def __init__(self, *arg, step, buffering = 16*MB) -> None:
        super().__init__(*arg, step=step)
        self.download_now = Event()
        self.download_now.set()
        self._buffering = buffering
        self._buffer_end = 0

    @property
    def buffer_start(self):
        return self._iter_process
    
    @property
    def buffer_end(self):
        return self._buffer_end
    
    @property
    def buffering(self):
        return self._buffering

    @property
    def control_end(self):
        return self._buffer_end
    
    @property
    def buffer_downloaded(self):
        '''返回缓存中已下载的内容占比'''
        return (self._process + self._start - self._iter_process) / self._buffering

    async def stream(self, block: Block):
        for chunk in super().stream(block):
            size = len(chunk)
            while block.process + size > self._buffer_end:
                self.download_now.clear()
                await self.download_now.wait()
            yield chunk
            
    async def download(self, block: Block):
        await super().download(block)
        await self.re_divition()

    async def re_divition(self):
        while not super().re_divition():
            await self.download_now.wait()
    async def __anext__(self):
        self.download_now.set()
        await super().__anext__()
    


class AllBase(DownloadBase, ABC):
    async def start(self):
        return await super().start()
    async def wait(self):
        await self.task_group.__aexit__()


class FileBase(DownloadBase, ABC):
    async def init(self):#<------------------------------------------------------------------------
        await super().init()
        self.aiofile = await aiofiles.open(self.file_name, 'w+b')
        self.file_lock = Lock()


class TempFileBase(DownloadBase, ABC):
    async def init(self):
        await super().init()
        self.temp_aiofile = await aiofiles.tempfile.TemporaryFile('w+b')
        self.file_lock = Lock()


class BytesBase(DownloadBase, ABC):
    def __init__(self, url, start: int = 0, stop: int | Inf = Inf()):
        super().__init__(url, start, stop)
        self._context = bytearray()
    

class ByteBuffer(BytesBase, BufferBase):

    async def stream(self, block: Block,/):
        async for chunk in super().stream(block):
            size = len(chunk)
            assert size < self._buffering
            off = block.process % self._buffering
            if off + size <= self._buffering:
                self._context[off: off + size] = chunk
            else:
                self._context[off:] = chunk[:off + size - self._buffering]
                self._context[off + size - self._buffering] = chunk[off + size - self._buffering:]
    
    async def __anext__(self):
        await super().__anext__()
        off = self._iter_process % self._buffering
        return self._context[off]


class fileBuffer(FileBase, BufferBase):

    async def stream(self, block: Block,/):
        async for chunk in super().stream(block):
            size = len(chunk)
            assert size < self._buffering
            off = block.process % self._buffering
            if off + size <= self._buffering:
                async with self.file_lock:
                    await self.aiofile.seek(off)
                    await self.aiofile.write(chunk)
            else:
                async with self.file_lock:
                    await self.aiofile.seek(off)
                    await self.aiofile.write(chunk[:off + size - self._buffering])
                    await self.aiofile.seek(0)
                    await self.aiofile.write(chunk[off + size - self._buffering:])

    async def __anext__(self):
        await super().__anext__()
        off = self._iter_process % self._buffering
        size = self.block_list[-1] - self._iter_process
        async with self.file_lock:
            await self.aiofile.seek(off)
            return await self.aiofile.read(self._iter_step)


class AllBytes(AllBase, BytesBase):
    async def wait(self):
        await super().wait()
        return self._context
    
    async def stream(self, block: Block):
        async for chunk in super().stream(block):
            size = len(chunk)
            self._context[block.process: block.process + size] = chunk

class AllFile(AllBase, FileBase):
    async def __init__(self, url, start: int = 0, stop: int | Inf = Inf()) -> None:
        super().__init__(url, start, stop)
        self.path = Path() / self.file_name

    async def wait(self):
        await super().wait()
        return self.path
    
    async def stream(self, block: Block):
        async for chunk in super().stream(block):
            async with self.file_lock:
                await self.aiofile.seek(block.process)
                await self.aiofile.write(chunk)


class StreamBytes(AllBytes, StreamBase):
    async def __anext__(self):
        super().__anext__()


class StreamFile(AllFile, StreamBase):
    async def __anext__(self):
        super().__anext__()
        async with self.file_lock:
            await self.aiofile.seek(self._iter_process)
            return await self.aiofile.read(self._iter_step)


class WebResouseStream(DownloadBase, StreamBase):
    '''旧的stream类,缺少继承,用作功能参考'''
    def __init__(self,*arg, step = 16*KB, buffering = 16*MB ) -> None:
        super().__init__(*arg)
        self._step = step
        self._buffering = buffering
        self._buffer_start = self._start
        self._buffer_end = self._buffer_start + buffering
        self._buffer = CircleFuffer(buffering)

        self.allow_iter = asyncio.Event()
        self.allow_download = asyncio.Event()
        self.allow_iter.set()
        self.allow_download.set()

    @property
    def iter_process(self):
        return self._buffer_start
    
    @iter_process.setter
    def iter_process(self, value):
        self._buffer_start = value
        self._buffer_end = self._buffer_start + self._buffering
    
    @property
    def buffer_end(self):
        return self._buffer_end
    
    @property
    def buffering(self):
        return self._buffering

    @property
    def control_end(self):
        #return min(self._stop, self._buffer_end)
        return self._buffer_end
    
    @property
    def buffer_downloaded(self):
        '''返回缓存中已下载的内容占比'''
        return (self._process + self._start - self._buffer_start) / self._buffering
    
    def iter_monitor(self):
        return SpeedMonitor(self,'_buffer_start')


    async def stream(self, block: Block):
        async for chunk in super().stream():
            len_chunk = len(chunk)
            #wait iter
            while block.process + len_chunk > self.buffer_end:
                self.allow_download.clear()
                await self.allow_download.wait()

            #write
            self._buffer.seek(block.process)
            self._buffer.write(chunk)

            #call iter  暂时没有结束检测
            if block == self.block_list[0] and block.process + len_chunk >= self.iter_process + self._step :
                self.allow_iter.set()
            if block == self.block_list[-1]:
                assert block is Inf or block.process == block.stop
                self.allow_iter.set()#结束检测
        while block.process + len_chunk > self.buffer_end:
            self.allow_download.clear()
            await self.allow_download.wait()
        self.block_list.remove(block)
    
    async def download(self, block):
        await super().download(self, block)
        await self.divition_wait()
    
    async def divition_wait(self):
        while not self.re_divition():
            await self.allow_download.wait()

    async def __anext__(self):
        if self.iter_process >= self._file_size:
            raise StopAsyncIteration
        if len(self.block_list) != 0 and self.iter_process + self._step > self.block_list[0].process:
            self.allow_iter.clear()
            await self.allow_iter.wait()
        self._buffer.seek(self.iter_process)
        if self.iter_process + self._step < self._file_size:
            i = self._buffer.read(self._step)#<-------bug：不会截断
            self.iter_process += self._step
        else:
            i = self._buffer.read(self._file_size - self.iter_process)
            self.iter_process = self._file_size
        self.allow_download.set()
        return i

    async def __aenter__(self):
        assert not self._entered
        self._entered = True
        self.task_group = await asyncio.TaskGroup().__aenter__()
        self.divition_task(0)
        async with self.init_prepare as res:
            self._handing_info(res)
            self._handing_name(res)
            self.block_list[-1].stop = self._file_size
        return self
    
    async def __aexit__(self, et, exv, tb):
        assert self._entered
        for i in self.task_group._tasks:
            i.cancel()
        await self.task_group.__aexit__()
        self._buffer = None
        return False
    
    def __aiter__(self):
        return self




    










