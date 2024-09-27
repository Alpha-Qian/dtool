import asyncio, httpx, aiofiles
from asyncio import Event, Lock
from collections import deque
from abc import ABC, abstractmethod

from .models import Inf, CircleFuffer
from .taskcoordinator import TaskCoordinator
from ._config import Range, Config, DEFAULTCONFIG, SECREAT
from ._exception import NotAcceptRangError, NotSatisRangeError
import time
client = httpx.AsyncClient(http2=True)

B = 1
KB = 1024
MB = 1048576
GB = 1073741824
TB = 1099511627776


class Block:
    __slots__ = ('process','stop','running')
    def __init__(self, process:int, end_pos:int|Inf = Inf, running:bool = True) -> None:
        if end_pos is None:
            end_pos = dtool.models.Inf()
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

import dtool.models as models

class DownloadBase(ABC):
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
        self._process = 0
        self._file_size = Inf()
        self._task_num = 0

        self.inited = False
        self.init_prepare = TaskCoordinator()
        self.headers = None
        self._accept_range = None


        self.resume = asyncio.Event()
        self.resume.set()

        self._entered = False
        self._exited = False

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
        #self.task_group.
        return len(self.task_group._tasks)
    
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
            self._handing_name(res)
            self.block_list[-1].stop = self._stop
            self.pre_divition(16)

    def pause(self):
        self.resume.clear()
    
    def unpause(self):
        self.resume.set()
    
    def close(self):
        '''断开所有连接'''
        for task in self.task_group._tasks:
            task.cancel()

    async def wait(self):
        await self.done_event.wait()
        await self.task_group.__aexit__(None, None, None)
    
    def speed_monitor(self):
        process = self._process
        t = time.time()
        while not self.done_event.is_set():
            dt = time.time() - t
            dp = self._process - process
            if dt != 0:
                yield dp/ dt
            else:
                yield 0
            process = self._process
            t = time.time()

    def monitor(self, size = 10):
        info = deque(size)
        while 1:
            process = self.process
            time_now = time()
            info.append((process, time_now))
            i = info[0]
            if time_now == i[1]:
                yield 0
            else:
                yield (process - i[0]) / (time_now - i[1])

    async def speed_limet(self, max_speed, monitor = None):
        '''短暂暂停以降低到速度限制'''
        monitor = models.SpeedMonitor(self)
        while not self.done_event.is_set():
            monitor.reset()
            yield
            speed, t = monitor.info()
            if speed > max_speed:
                sleep_time = (speed / max_speed - 1) * t
                self.pause()
                asyncio.get_running_loop().call_later(sleep_time, self.unpause)

    def new_monitor(self):
        return models.SpeedMonitor(self)

    def pre_divition(self,  block_num):
        if self._start > self.control_end:
            raise RuntimeError
        block_size = ( self.control_end - self._start ) // block_num
        if block_num != 0:
            for i in range(self._start + block_size, self.control_end - block_num, block_size):
                self.divition_task(i)

    def re_divition(self) -> bool:
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
        self.headers = res.headers
        self._accept_range = 'accept-ranges' in res.headers and res.headers['accept-ranges'] == 'bytes' or res.status_code == httpx.codes.PARTIAL_CONTENT
        if 'content-range' in res.headers and (size := res.headers['content-range'].split('/')[-1]) != '*' :
            #标准长度获取
            self._file_size = int(size)
        elif 'content-length' in res.headers and ( 'content-encoding' not in res.headers or res.headers['content-encoding'] == 'identity' ):
            res.iter_bytes
            #仅适用于无压缩数据，http2可能不返回此报头
            self._file_size = int(res.headers['content-length'])
        else:
            self._file_size = models.Inf()
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
    async def handing_stream(self, block:Block):
        pass
    

    async def range_stream(self, block:Block):
        raw_block = Block()
        for chunk in self.stream(raw_block):
            size = len(chunk)
            if raw_block.process > block.process:
                block.process = raw_block.process
                yield chunk
            elif size + raw_block.process > block.process:
                yield chunk[block.process - raw_block.process:]

    @abstractmethod   
    async def download(self, block:Block):
        if block.running:
            return
        block.running = True
        try:
            stream = self.stream(block)
            async for chunk in stream:
                pass
        except asyncio.CancelledError:
            pass
        except httpx.TimeoutException:
            pass
        else:
            self.block_list.remove(block)
            if len(self.block_list) == 0:
                pass
        finally:
            pass
        await stream.aclose()
        block.running = False

class WebResouseStream(DownloadBase, StreamBase):

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
        return models.SpeedMonitor(self,'_buffer_start')


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
                assert block is models.Inf or block.process == block.stop
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


@ABC
class StreamBase(DownloadBase, ABC):
    '''重写__init__, __aiter__, __aenter__, __aexit__的行为'''
    def __init__(self, *arg, **kwarg) -> None:
        super().__init__(*arg, **kwarg)
        self.wait_download = Event()
        self.wait_download.set()

    def __aiter__(self):
        return self
    
    async def __aenter__(self):
        assert not self._entered
        self._entered = True
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
    
    @property
    def iter_process(self):
        return
        return self._buffer_start
    
    def re_divition(self) -> bool:
        pass

class BufferBase(DownloadBase, ABC):

    def __init__(self, *arg, **kwarg) -> None:
        super().__init__(*arg, **kwarg)
        self.wait_iter = Event()
        self.wait_download = Event()
        self._step = 
        self.buffering = 
        self.buffer_start = 
        self.buffer_end = 
        self._buffer = CircleFuffer(self.buffering)
        self.wait_iter.set()
        self.wait_download.set()
    
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

    async def stream(self, block: models.Block):
        for chunk in super().stream(block):
            size = len(chunk)
            while block.process + size > self.buffer_end:
                self.wait_iter.clear()
                await self.wait_iter.wait()
            yield chunk
            if block == self.block_list[0] and block.process + size >= self.iter_process + self._step :
                self.wait_download.set()
    
    async def divition_wait(self):
        while not self.re_divition():
            await self.wait_iter.wait()

    async def __anext__(self):
        #await self.wait_init.wait()
        #wait download
        if self.iter_process >= self._file_size:
            raise StopAsyncIteration
        if len(self.block_list) != 0 and self.iter_process + self._step > self.block_list[0].process:
            self.wait_download.clear()
            await self.wait_download.wait()#bug:完成后会一直wait

        #read
        self._buffer.seek(self.iter_process)
        if self.iter_process + self._step < self._file_size:
            i = self._buffer.read(self._step)#<-------bug：不会截断
            self.iter_process += self._step
        else:
            i = self._buffer.read(self._file_size - self.iter_process)
            self.iter_process = self._file_size

        #call download
        self.wait_iter.set()
        #if self.block_list[-1]
        return i

class AllBase(DownloadBase, ABC):
    pass

class FileBase(DownloadBase, ABC):
    async def init(self):
        self.aiofile = await aiofiles.open(self.file_name, 'w+b')

    async def stream(self, block: Block):
        async for chunk in super().stream(block):
            await self.aiofile.seek(block.process)
            await self.aiofile.write(chunk)
            yield

class BytesBase(DownloadBase, ABC):
    async def __init__(self, url, start: int = 0, stop: int | Inf = Inf()) -> None:
        super().__init__(url, start, stop)
        self.context = bytearray()


class ByteBuffer(BytesBase, BufferBase):
    async def download(self, block: Block):
        await super().download(block)

    async def stream(self, block: models.Block):
        async for chunk in super().stream(block)

class fileBuffer(FileBase, BufferBase):
    pass


class AllBytes(AllBase, BytesBase):
    pass

class AllFile(AllBase, FileBase):
    pass




class StreamBytes(AllBytes, StreamBase):
    pass

class StreamFile(AllFile, StreamBase):
    pass



    










