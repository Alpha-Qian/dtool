import asyncio, httpx, aiofiles
import enum
from pathlib import Path
from asyncio import Event, Lock
from collections import deque
from abc import ABC, abstractmethod
from pathlib import Path
httpx.Auth
from .models import Inf, SpeedMonitor, BufferSpeedMoniter, SpeedInfo, SpeedCacher
from ._config import Config, DEFAULTCONFIG, SECREAT
from ._exception import NotAcceptRangError, NotSatisRangeError
import time
client = httpx.AsyncClient(limits=httpx.Limits())

B = 1
KB = 1024
MB = 1048576
GB = 1073741824
TB = 1099511627776

class HeadersName(enum.Enum):
    ACCEPT_RANGES = 'accept-ranges'
    CONTECT_RANGES = 'contect-ranges'
    CONTECT_LENGTH = 'content-length'
    CONTECT_TYPE = 'content-type'
    
    CONTECT_DISPOSITION = 'content-disposition'
    RANGES = 'ranges'



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


class PoolBase(ABC):
    '''基础控制策略'''

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

    def download_prepare(self, res):
        pass

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


class DownloadBase(ABC):
    ''' 基本控制策略'''

    def __init__(self, url, start:int = 0, stop:int|Inf = Inf(),/) -> None:
        self.client = httpx.AsyncClient(limits=httpx.Limits())
        self.url = url
        self.block_list:list[Block] = []
        
        self._start = start
        self._stop = stop
        self._process = start
        self._file_size = Inf()

        self.inited = False
        #self.init_prepare = TaskCoordinator()#待删除
        self._headers = None
        self._accept_range = None

        self._started = False
        self._closed = False

        self._task_num = 0
        self.resume = Event()
        self.resume.set()

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
        while not self._done.is_set():
            yield SpeedInfo(self._process - process, time.time() - t)
            process = self._process
            t = time.time()
        
    def buffer_monitor(self, size = 10):
        info = deque(size + 1)
        while not self._closed:
            process = self.process
            time_now = time.time()
            info.append((process, time_now))
            i = info[0]
            yield SpeedInfo(process - i[0], time_now - i[1])

    def auto_create(self,  threshold=0.1, accuracy=0.1):
        '''自动在需要时创建任务'''
        while 1:
            max_speed_per_thread = 0
            speed_info:SpeedInfo = yield
            max_


    async def daemon_coro(self,*, auto = True, speed_limit = Inf(), sleep_time = 0):
        '''main coro'''
        self.divition_task(self._start)
        gen = self.buffer_monitor(10)
        if auto:
            cacher = SpeedCacher(self.speed_monitor(), 10)
        for info in gen:
            if not self.resume.is_set():
                #跟随暂停
                on_stop_time = time.time()
                await self.resume
                resume_time = time.time()

            asyncio.sleep(sleep_time)
            if self.check_speed(info):
                await self.re_divition()
            # or...
            await self.check_speed(info)
            self.speed_limet(speed_limit, info)

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

    def download_prepare(self, res:httpx.Response):
        '''第一次成功连接后初始化下载参数'''
        self.inited = True
        self._headers = res.headers
        self._accept_range = res.headers.get('accept-ranges') == 'bytes' or res.status_code == httpx.codes.PARTIAL_CONTENT
        if 'content-range' in res.headers and (size := res.headers['content-range'].split('/')[-1]) != '*' :
            #标准长度获取
            self._file_size = int(size)
        elif 'content-length' in res.headers and res.headers.get('content-length','identity') == 'identity':
            #仅适用于无压缩数据，http2可能不返回此报头
            self._file_size = int(res.headers['content-length'])
        else:
            self._file_size = Inf()
            self._accept_range = False
            if self._accept_range:
                #允许续传，但无法获得文件长度，所以发送res的请求时headers应添加'range: bytes=0-'不然服务器不会返回'content-range'
                self._accept_range = False
                raise RuntimeWarning()
            
        
        import re
        import urllib.parse
        from email.utils import decode_rfc2231

        contect_disposition = res.headers.get(HeadersName.CONTECT_DISPOSITION, default = '')
        if match := re.search(r'filename\*\s*=\s*([^;]+)', contect_disposition, re.IGNORECASE):
            name = decode_rfc2231(match.group(1))
            name = urllib.parse.unquote(name[2])  # fileName* 后的部分是编码信息
            print('')

        elif match := re.search(r'filename\s*=\s*["\']?([^"\';]+)["\']?', contect_disposition, re.IGNORECASE):
            name = match.group(1)

        elif name:= httpx.QueryParams(res.url.query).get('response-content-disposition',default = '').split("filename=")[-1]:
            name = name.split()
            # 去掉可能存在的引号    
            if name.startswith('"') and name.endswith('"'):
                name = name[1:-1]
            elif name.startswith("'") and name.endswith("'"):
                name = name[1:-1]
            self.file_name = name

        elif name := res.url.path.split('/')[-1]:
            self.file_name = name

        else:
            content_type = res.headers["content-type"].split('/')[-1]
            fileName = f"downloaded_file{int(time.time())}.{content_type}"#TODO 格式化时间
        
        self._stop = min(self._stop, self._file_size)
        self.block_list[-1].stop = self._stop
        self.pre_divition(16)
        
    async def stream(self, block:Block):
        '''基础网络获取生成器,会修改block处理截断和网络错误'''
        await self.resume.wait()
        headers = {"Range": f"bytes={block.process}-"}
        async with client.stream('GET',self.url,headers = headers) as response:
            if response.status_code == 416:
                raise NotSatisRangeError
            response.raise_for_status()

            if not self.inited:
                self.download_prepare(response)

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


    async def start(self):
        self.task_group = await asyncio.TaskGroup().__aenter__()
        self.divition_task(self._start)
        self.deamon = asyncio.create_task(self.daemon_coro(auto=0, speed_limit=0 ,sleep_time=0 ))

    
    async def aclose(self):
        '''断开所有连接'''
        self.deamon.cancel()
        for task in self.task_group._tasks:
            task.cancel()
        await self.client.aclose()
        self._closed = True

    async def wait(self):
        await self.task_group.__aexit__(None, None, None)
        await self.aclose()
    
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
                self._done.set()
        finally:
            self._task_num -= 1
            block.running = False


class DeamonBase(DownloadBase, ABC):
    
    async def start(self):
        await super().start()
        self.deamon = asyncio.create_task(self.daemon_coro(auto=0, speed_limit=0 ,sleep_time=0 ))

    async def aclose(self):
        self.deamon.cancel()
        await super().aclose()
    
class StreamBase(DownloadBase, ABC):
    '''基本流式控制策略，没有缓冲大小限制'''
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
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, et, exv, tb):
        for i in self.task_group._tasks:
            i.cancel()
        await self.task_group.__aexit__()
        self._buffer = None
        return False
    
    async def __aiter__(self):
        return self.aiter()

    
    async def aiter(self):
        await self.start()
        while self.iter_process < self._stop:
            if len(self.block_list) != 0 and self.iter_process + self._iter_step > self.block_list[0].process:
                self.iter_now.clear()
                await self.iter_now.wait()
            yield
        await self.aclose()

    def re_divition(self) -> bool:
        pass


class BufferBase(StreamBase):
    '''有缓冲大小限制的基本策略'''
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
    
    @StreamBase.iter_process.setter
    def iter_process(self, value):
        self._iter_process = value
        self._buffer_end = self._iter_process + self._buffering###

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
        self.download_now.set()#这行放在super前可能会有问题
        await super().__anext__()

    async def aiter(self):
        for i in super().aiter():
            yield
            self.download_now.set()

class AllBase(DownloadBase, ABC):
    '''完全下载策略'''
    async def __await__(self):
        await self.wait()


class FileBase(DownloadBase, ABC):
    '''写入文件策略'''
    def __init__(self, url, start: int = 0, stop: int | Inf = Inf(), path:Path = Path(), name = None) -> None:
        super().__init__(url, start, stop)
        self.path = path
        self.file_name = name

    async def start(self):
        await super().start()
        self.aiofile = await aiofiles.open(self.file_name, 'w+b')#会清除为空文件
        self.file_lock = Lock()

    async def restart(self, path:Path):
        self.aiofile = await aiofiles.open(path, '+ab')

class TempFileBase(DownloadBase, ABC):
    '''使用临时文件策略'''

    async def start(self):
        await super().start()
        self.tempfile = await aiofiles.tempfile.TemporaryFile('w+b')
        self.file_lock = Lock()

    async def aclose(self):
        await super().aclose()
        await self.tempfile.close()


class BytesBase(DownloadBase, ABC):
    '''使用内存策略'''
    def __init__(self, url, start: int = 0, stop: int | Inf = Inf()):
        super().__init__(url, start, stop)
        self._context = bytearray()
    
class IterBytes(StreamBase, TempFileBase):
    async def aiter(self):
        for i in super().aiter():
            yield

class IterFile(StreamBase, BytesBase):
    async def aiter(self):
        async for i in super().aiter():
            yield

class ByteBuffer(BufferBase):
    '''用内存缓冲'''

    async def stream(self, block: Block,/):
        async for chunk in super().stream(block):
            size = len(chunk)
            assert size < self._buffering
            off = block.process % self._buffering
            if off + size <= self._buffering:
                self._buffer[off: off + size] = chunk
            else:
                self._buffer[off:] = chunk[:off + size - self._buffering]
                self._buffer[off + size - self._buffering] = chunk[off + size - self._buffering:]
    
    async def __anext__(self):
        await super().__anext__()
        off = self._iter_process % self._buffering
        return self._buffer[off]
    
    async def start(self):
        await super().start()
        self._buffer = bytearray()

    async def aclose(self):
        await super().aclose()
        self._buffer = bytearray()

    async def aiter(self):
        async for i in super().aiter():
            off = self._iter_process % self._buffering
            yield self._buffer[off] 


class fileBuffer(BufferBase):
    '''用临时文件缓冲'''
    async def stream(self, block: Block,/):
        async for chunk in super().stream(block):
            size = len(chunk)
            assert size < self._buffering
            off = block.process % self._buffering
            if off + size <= self._buffering:
                async with self.file_lock:
                    await self.tempfile.seek(off)
                    await self.tempfile.write(chunk)
            else:
                async with self.file_lock:
                    await self.tempfile.seek(off)
                    await self.tempfile.write(chunk[:off + size - self._buffering])
                    await self.tempfile.seek(0)
                    await self.tempfile.write(chunk[off + size - self._buffering:])

    async def __anext__(self):
        await super().__anext__()
        off = self._iter_process % self._buffering
        size = self.block_list[-1] - self._iter_process
        async with self.file_lock:
            await self.tempfile.seek(off)
            return await self.tempfile.read(self._iter_step)
        
    async def start(self):
        await super().start()
        self.tempfile = await aiofiles.tempfile.TemporaryFile('w+b')
        self.file_lock = Lock()

    async def aclose(self):
        await super().aclose()
        await self.tempfile.close()

    async def aiter(self):
        for i in super().aiter():
            off = self._iter_process % self._buffering
            #size = self.block_list[-1] - self._iter_process
            async with self.file_lock:
                await self.tempfile.seek(off)
                return await self.tempfile.read(self._iter_step)


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
    
    async def reload(self, path:Path):
        pass
    
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

