import asyncio, httpx, aiofiles
import enum
from pathlib import Path
from asyncio import Event, Lock
from abc import ABC, abstractmethod
from pathlib import Path
from . import models
from .models import Inf, SpeedMonitor, BufferSpeedMoniter, SpeedInfo, SpeedCacher
from ._exception import NotAcceptRangError, NotSatisRangeError
import time
import re
import urllib.parse
from email.utils import decode_rfc2231
client = httpx.AsyncClient(limits=httpx.Limits())

B = 1
KB = 1024
MB = 1048576
GB = 1073741824
TB = 1099511627776


class HeadersName(enum.StrEnum):
    ACCEPT_RANGES = "accept-ranges"
    CONTECT_RANGES = "contect-ranges"
    CONTECT_LENGTH = "content-length"
    CONTECT_TYPE = "content-type"
    CONTECT_DISPOSITION = "content-disposition"
    RANGES = "ranges"


class Block:
    __slots__ = ("process", "stop", "_task")

    def __init__(
        self, process: int, end_pos: int | Inf = Inf()) -> None:
        self.process = process
        self.stop = end_pos
    
    @property
    def running(self):
        if hasattr(self, "_task"):
            return not self._task.done()
        else:
            return False

    @property
    def task(self):
        if hasattr(self, "_task"):
            return self._task
        else:
            raise AttributeError("task not set")

    @task.setter
    def task(self, value:asyncio.Task):
        if not self.running:
            self._task = value
        else:
            self._task.cancel()
            self._task = value

    def cancel_task(self):
        self._task.cancel()

    def __str__(self) -> str:
        return f"{self.process}-{self.stop}"

    def __getstate__(self):
        return (self.process, self.stop)

    def __setstate__(self, state: tuple):
        self.process, self.stop = state


class DownloadBase(ABC):
    """基本控制策略 处理各种基本属性"""

    @abstractmethod
    def __init__(self, url, task_num = 16, chunk_size = None, blocks:None|list[Block] = None):

        self.client = httpx.AsyncClient(limits=httpx.Limits())
        self.url = url
        self.chunk_size = chunk_size
        self.task_group = asyncio.TaskGroup()
        self.inited_event = asyncio.Event()
        
        self.pre_divition_num = task_num

        self.inited = False
        self._accept_range = False
        self._contect_length: int | Inf = Inf()
        self._contect_name = None

        self._task_num = 0
        self._stop_divition_task = False
        self._resume = Event()  # 仅内部使用
        self._resume.set()

        self._process = 0
        self._stop = 0
        if blocks is None:
            self._block_list = [Block(0,None)]
        else:
            self._block_list = blocks

        for i in self._block_list:
            self._stop += i.stop - i.process

    def cancel_one_task(self , min_remain = MB):
        """取消一个最多剩余的任务"""
        match = False
        max_remain = 0
        min_remain = MB
        for block in self._block_list:
            if block.running and block.stop - block.process > max_remain:
                match = True
                max_remain = block.stop - block.process
                max_remain_block = block
                return
        if match and max_remain > min_remain:
            max_remain_block.cancel_task()

    @abstractmethod
    async def on_task_exit(self):
        """任务完成回调"""
        raise NotImplementedError

    def start_block(self, block:Block):
        block.task = self.task_group.create_task(self.download(block))
        self._task_num += 1

    def _init(self, res: httpx.Response):
        """统一的初始化步骤,包括第一次成功连接后初始化下载参数,并创建更多任务,不应该被重写"""
        assert not self.inited
        self.inited = True
        self._headers = res.headers
        self._accept_range = (
            res.headers.get(HeadersName.ACCEPT_RANGES) == "bytes"
            or res.status_code == httpx.codes.PARTIAL_CONTENT
        )
        if (
            HeadersName.CONTECT_RANGES in res.headers
            and (size := res.headers[HeadersName.CONTECT_RANGES].split("/")[-1]) != "*"
        ):
            # 标准长度获取
            self._contect_length = int(size)
        elif (
            HeadersName.CONTECT_LENGTH in res.headers
            and res.headers.get(HeadersName.CONTECT_LENGTH, "identity") == "identity"
        ):
            # 仅适用于无压缩数据，http2可能不返回此报头
            self._contect_length = int(res.headers[HeadersName.CONTECT_LENGTH])
        else:
            self._contect_length = Inf()
            self._accept_range = False
            if self._accept_range:
                # 允许续传，但无法获得文件长度，所以发送res的请求时headers应添加'range: bytes=0-'不然服务器不会返回'content-range'
                self._accept_range = False
                raise RuntimeWarning()

        contect_disposition = res.headers.get(
            HeadersName.CONTECT_DISPOSITION, default=""
        )
        if match := re.search(
            r"filename\*\s*=\s*([^;]+)", contect_disposition, re.IGNORECASE
        ):
            name = decode_rfc2231(match.group(1))[2]
            name = urllib.parse.unquote(name)  # fileName* 后的部分是编码信息

        elif match := re.search(
            r'filename\s*=\s*["\']?([^"\';]+)["\']?', contect_disposition, re.IGNORECASE
        ):
            name = match.group(1)

        elif (
            name := httpx.QueryParams(res.url.query)
            .get("response-content-disposition", default="")
            .split("filename=")[-1]
        ):
            name = name.split()
            # 去掉可能存在的引号
            if name.startswith('"') and name.endswith('"'):
                name = name[1:-1]
            elif name.startswith("'") and name.endswith("'"):
                name = name[1:-1]
            fileName = name

        elif name := res.url.path.split("/")[-1]:
            fileName = name

        else:
            content_type = res.headers["content-type"].split("/")[-1]
            fileName = (
                f"downloaded_file{int(time.time())}.{content_type}"  # TODO 格式化时间
            )

        self._contect_name = fileName
        self._stop = min(self._stop, self._contect_length)
        self._block_list[-1].stop = self._stop

        if self._accept_range:
            pass

    async def stream(self, block: Block):  # 只在基类中重载
        """基础流式获取生成器,会修改block处理截断和网络错误,第一个创建的任务会自动执行下载初始化,决定如何处理数据"""
        await self._resume.wait()
        headers = {"Range": f"bytes={block.process}-"}
        async with client.stream("GET", self.url, headers=headers) as response:
            if response.status_code == 416:
                raise NotSatisRangeError
            response.raise_for_status()

            if not self.inited:
                self._init(response)

            async for chunk in response.aiter_raw(chunk_size = self.chunk_size):
                len_chunk = len(chunk)
                if block.process + len_chunk < block.stop:
                    await self._handing_chunk(block, chunk, len_chunk)
                    self._process += len_chunk
                    block.process += len_chunk
                else:
                    #len_chunk = block.stop - block.process
                    await self._handing_chunk(block, chunk[: block.stop - block.process], block.stop - block.process)
                    self._process += block.stop - block.process
                    block.process = block.stop
                    break
                await self._resume.wait()
    
    @abstractmethod
    async def _handing_chunk(self, block:Block, chunk:bytes, chunk_size:int):
        raise NotImplementedError
    
    @abstractmethod
    async def _write_chunk(self, block:Block, chunk:bytes, chunk_size:int):
        raise NotImplementedError

    @abstractmethod
    async def _get_buffer(self, process: int, step: int) -> bytes:
        '''仅在StreamBase及其子类中会被调用,不负责截断，不保证内容是否合法'''
        raise NotImplementedError


    async def start_coro(self):
        """开始任务拓展，用于子类"""
        pass

    async def cancel_coro(self):
        """取消任务拓展，用于子类"""
        pass

    async def close_coro(self):
        """关闭任务拓展，用于子类"""
        pass

    async def deamon(self):
        """守护进程拓展，用于子类，监控下载进度等"""
        return

    async def main(self):
        """主函数，负责启动异步任务和处理错误."""
        try:
            async with self.task_group:
                await self.start_coro()
                block = Block(0,)
                self._block_list = [block]
                self.start_block(block)
                asyncio.gather(self.deamon())

        except asyncio.CancelledError:
            await self.cancel_coro()

        finally:
            await self.client.aclose()
            await self.close_coro()

    def diviton_task(self, times:int = 1):
        '''相当于运行times次__reassignWorker,但效果更好。在只有一个worker时相当于__clacDivisionalWorker'''
        count:dict[Block,int] = {}
        for block in self._block_list:
            count[block] = 1 if block.running else 0
        
        for i in range(times):#查找分割times次的最优解
            maxremain = 0
            maxblock = None
            for block in self._block_list:
                if (remain := ( block.stop - block.process ) / ( count[block] + 1 )) > maxremain:
                    maxremain = remain
                    maxblock = block

            if maxremain < 1024 ** 2:
                break
            
            if maxblock is not None:
                count[maxblock] += 1

        for block, divitionTimes in count.items():#根据最优解创建线程

            if not block.running and divitionTimes >= 1:#检查是否需要启动work
                self.start_block(block)

            if divitionTimes >= 2:#检查是否需要分割并添加新worker
                size = (block.stop - block.process) // divitionTimes
                index = self._block_list.index(block)
                for j in range(1, divitionTimes):
                    index += 1
                    start = block.process + j * size
                    end = block.process + (j + 1) * size
                    _ = Block(start,end)
                    self._block_list.insert(index, _)
                    self.start_block(_)
                _.stop = block.stop
                block.stop = block.process + size

    async def deamon_auto(self, check_time = 1):
        while True:
            await asyncio.sleep(check_time)

    async def deamon_default(self, check_time = 1):
        while True:
            await asyncio.sleep(check_time)
            if self._task_num < 16:
                self.diviton_task(16 - self._task_num) 

    async def download(self, block: Block):
        """统一的下载任务处理器,会修改block状态,不应该被重写"""
        try:
            await self.stream(block)
        except Exception:
            #Exception 不包括CancelledError
            await self.on_task_exit()

        else:
            await self.on_task_exit()
            self._block_list.remove(block)

        finally:
            self._task_num -= 1


class AllBase(DownloadBase):
    """一次性获取所有内容"""

    def __init__(self, url, task_num = 16, chunk_size = None, blocks:None|list[Block] = None) -> None:
        super().__init__(url, task_num, chunk_size, blocks)
        

    async def _handing_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        await self._write_chunk(block, chunk, chunk_size)

    def run(self):
        """启动下载"""
        asyncio.run(self.main())
    
class StreamBase(DownloadBase):
    """基本流式控制策略，没有缓冲大小限制"""

    def __init__(self, url, task_num = 16, chunk_size = None, blocks:None|list[Block] = None, start, step) -> None:
        super().__init__(url,task_num, chunk_size)
        self.iterable = Event()
        self._iter_process = start
        self.next_iterable_check_point = start + step 
        self._iter_step = step

    async def _handing_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        await self._write_chunk(block, chunk, chunk_size)
        if block.process < self.next_iterable_check_point <= block.process + chunk_size:
            self.iterable.set()

    async def __aiter__(self):
        """异步迭代器, 负责截断，保证内容是否合法'''"""
        while self._iter_process < self._stop:
            if (
                len(self._block_list) > 0
                and  self._iter_process + self._iter_step > self._block_list[0].process
            ):
                self.next_iterable_check_point = self._iter_process + self._iter_step
                self.iterable.clear()
                await self.iterable.wait()

            chunk = yield await self._get_buffer(self._iter_process, self._iter_step)

            if len(chunk) + self._iter_process > self._stop:
                chunk = chunk[: self._stop - self._iter_process]
            self._iter_process += len(chunk)

            yield chunk



    def iter(self):
        raise NotImplementedError
        if asyncio._get_running_loop() is not None:
            raise RuntimeError('Use "async for" in async context')
        """同步迭代器"""
        while self.iter_process < self._stop:
            if (
                len(self._block_list) != 0
                and self.iter_process + self._iter_step > self._block_list[0].process
            ):
                self.iterable.clear()
                if not self._loop.is_running():
                    self._loop.run_until_complete(self.iterable.wait())
            yield


class BufferBase(StreamBase):
    """有缓冲大小限制的基本策略"""

    def __init__(self, *arg, step, buffering=16 * MB) -> None:
        super().__init__(*arg, step=step)
        self.downloadable = Event()
        self.next_downloadable_check_point = self._start
        self._buffering = buffering
        self._buffer_end = 0
        if self._block_list[-1].process > self._iter_process + buffering:
            raise ValueError

    async def _handing_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        #因为缓冲区外的块理论上不会被执行，所以不用考虑超出缓冲区的块，只用考虑最靠近缓冲区末尾的块
        while block.process > self._iter_process + self._buffering:#检查是否在缓冲区外，在缓冲区外一直等待
            await self.downloadable.wait()

        if block.process + chunk_size > self._iter_process + self._buffering:#检查下一次写入数据会不会超出缓冲区
            self.next_downloadable_check_point = block.process + chunk_size - self._buffering
            self.downloadable.clear()
            await self.downloadable.wait()
        
            if self._block_list[-1] != block:
                i = self._block_list.index(block) + 1
                self.next_downloadable_check_point = self._block_list[i].process - self._buffering

        await StreamBase._handing_chunk(self, block, chunk, chunk_size)


    def diviton_task(self, times: int = 1):
        '''相比DownloadBase的分割策略，BufferBase的分割策略更加复杂，需要考虑缓冲区的限制。'''
        count:dict[Block,int] = {}
        for block in self._block_list:
            count[block] = 1 if block.running else 0
        
        for i in range(times):#查找分割times次的最优解
            maxremain = 0
            maxblock = None

            for block in self._block_list:
                if block.process > self._iter_process + self._buffering: #忽略超出缓冲区的块
                    break
                if (remain := ( min(block.stop, self._iter_process + self._buffering)#只计算缓冲区内的剩余进度
                                - block.process ) / ( count[block] + 1 )) > maxremain:
                    maxremain = remain
                    maxblock = block

            if maxremain < 1024 ** 2:
                break
            
            if maxblock is not None:
                count[maxblock] += 1

        for block, divitionTimes in count.items():#根据最优解创建线程

            if not block.running and divitionTimes >= 1:#检查是否需要启动work
                self.start_block(block)

            if divitionTimes >= 2:#检查是否需要分割并添加新worker
                size = (block.stop - block.process) // divitionTimes
                index = self._block_list.index(block)
                for j in range(1, divitionTimes):
                    index += 1
                    start = block.process + j * size
                    end = block.process + (j + 1) * size
                    _ = Block(start,end)
                    self._block_list.insert(index, _)
                    self.start_block(_)
                _.stop = block.stop
                block.stop = block.process + size

    
    async def __aiter__(self):
        async for chunk in StreamBase.__aiter__(self):
            yield chunk
            if self._iter_process >= self.next_downloadable_check_point:
                self.downloadable.set()

class CircleBufferBase(BufferBase):
    '''循环队列缓冲，需要检查缓冲区长度是否符合要求'''
    #这种数据结构通常被称为 环形缓冲区（Circular Buffer）或 循环队列（Circular Queue）。它非常适合用于数据流的写入和读取，特别是在内存受限的场景中。
    def __init__(self, *arg, step, buffering=16 * MB) -> None:
        BufferBase.__init__(self, *arg, step=step, buffering=buffering)
        if self._block_list[-1].process > self._iter_process + buffering:
            raise ValueError

class FileBase(DownloadBase, ABC):
    """写入(异步）文件策略"""

    def __init__(
        self,
        url,
        path: Path = Path(),
        name=None,
    ) -> None:
        super().__init__(url)
        self.path = path
        self.file_name = name

    async def _write_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        async with self.file_lock:
            await self.aiofile.seek(block.process)  
            await self.aiofile.write(chunk)

    async def _get_buffer(self, process: int, step: int):
        async with self.file_lock:
            await self.aiofile.seek(process)
            return await self.aiofile.read(step)
    
    async def start_coro(self):
        await super().start_coro()
        self.aiofile = await aiofiles.open(self.file_name, "w+b")  # 会清除为空文件
        self.file_lock = Lock()

class TempFileBase(DownloadBase):
    """使用（异步）临时文件策略"""

    async def start_coro(self):
        await super().start_coro()
        self.tempfile = await aiofiles.tempfile.TemporaryFile("w+b")
        self.file_lock = Lock()

    async def close_coro(self):
        await super().close_coro()
        await self.tempfile.close()


class BytesBase(DownloadBase, ABC):
    """使用内存策略"""

    async def _init(self, res: httpx.Response):
        super()._init(res)
        self._context = bytearray(self._contect_length)

    async def _write_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        self._context[block.process : block.process + chunk_size] = chunk

    async def _get_buffer(self, process: int, step: int):
        return self._context[process : process + step]

class CircleByteBuffer(CircleBufferBase):
    """用内存缓冲"""

    async def _write_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        assert chunk_size < self._buffering
        off = block.process % self._buffering
        if off + chunk_size <= self._buffering:
            self._buffer[off : off + chunk_size] = chunk
        else:
            self._buffer[off:] = chunk[: off + chunk_size - self._buffering]
            self._buffer[off + chunk_size - self._buffering] = chunk[
                off + chunk_size - self._buffering :
            ]

    async def __anext__(self):
        await super().__anext__()
        off = self._iter_process % self._buffering
        return self._buffer[off]

    async def start_coro(self):
        await super().start_coro()
        self._buffer = bytearray()

    async def close_coro(self):
        await super().close_coro()
        self._buffer = bytearray()
    
    async def _get_buffer(self):
        off = self._iter_process % self._buffering
        if off + self._iter_step <= self._buffering:
            c = self._buffer[off : off + self._iter_step]
        else:
                c = self._buffer[off : ]
                c += self._buffer[ : off + self._iter_step - self._buffering]
        if 0 < self._stop - self._iter_process < self._iter_step:
            c = c[:self._stop - self._iter_process]
        return c


class fileBuffer(CircleBufferBase, TempFileBase):
    """用临时文件缓冲"""

    async def _write_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        off = block.process % self._buffering
        if off + chunk_size <= self._buffering:
            async with self.file_lock:
                await self.tempfile.seek(off)
                await self.tempfile.write(chunk)
        else:
            async with self.file_lock:
                await self.tempfile.seek(off)
                await self.tempfile.write(chunk[: off + chunk_size - self._buffering])
                await self.tempfile.seek(0)
                await self.tempfile.write(chunk[off + chunk_size - self._buffering :])


    async def start_coro(self):
        await super().start_coro()
        self.tempfile = await aiofiles.tempfile.TemporaryFile("w+b")
        self.file_lock = Lock()

    async def close_coro(self):
        await super().close_coro()
        await self.tempfile.close()

    async def __aiter__(self):
        for i in super().__aiter__():
            off = self._iter_process % self._buffering
            async with self.file_lock:
                await self.tempfile.seek(off)
                return await self.tempfile.read(self._iter_step)
            
    async def _get_buffer(self):
        off = self._iter_process % self._buffering
        if off + self._iter_step <= self._buffering:
            async with self.file_lock:
                await self.tempfile.seek(off)
                chunk = await self.tempfile.read(self._iter_step)
        else:
            async with self.file_lock:
                await self.tempfile.seek(off)
                chunk = await self.tempfile.read()
                await self.tempfile.seek(0)
                chunk = chunk + await self.tempfile.read(off + self._iter_step - self._buffering)
        if 0 < self._stop - self._iter_process < self._iter_step:
            chunk = chunk[:self._stop - self._iter_process]
        return chunk


class UncircleBytes(BufferBase):

    def __init__(self, *arg, step, buffering=16 * MB) -> None:
        super().__init__(*arg, step=step, buffering=buffering)
        self.buffers = {block:bytearray() for block in self._block_list}

    async def _write_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        self.buffers[block] += chunk

    async def _get_buffer(self):
        return NotImplemented

class AllBytes(AllBase, BytesBase):
    """下载所有内容并保存在内存中"""

    async def _write_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        self._context[block.process : block.process + chunk_size] = chunk
