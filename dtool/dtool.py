import asyncio, httpx, aiofiles
import enum
from pathlib import Path
from asyncio import Event, Lock
from abc import ABC, abstractmethod
from pathlib import Path
from .models import Inf, SpeedMonitor, BufferSpeedMoniter, SpeedInfo, SpeedCacher
from ._config import Config, DEFAULTCONFIG, SECREAT
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
    __slots__ = ("process", "stop", "running")

    def __init__(
        self, process: int, end_pos: int | Inf = Inf(), running: bool = True
    ) -> None:
        self.process = process
        self.stop = end_pos
        self.running = False

    def __str__(self) -> str:
        return f"{self.process}-{self.stop}"

    def __getstate__(self):
        return (self.process, self.stop)

    def __setstate__(self, state: tuple):
        self.process, self.stop = state
        self.running = False


class DownloadBase(ABC):
    """基本控制策略 处理各种基本属性"""

    @abstractmethod
    def __init__(
        self, url, start: int = 0, stop: int | Inf = Inf(), task_num=16, /
    ) -> None:
        self.client = httpx.AsyncClient(limits=httpx.Limits())
        self.url = url
        self.task_group = asyncio.TaskGroup()
        self._block_list: list[Block] = []
        self.pre_divition_num = task_num

        self._start = start
        self._stop = stop
        self._process = start
        self._contect_length: int | Inf = Inf()
        self._contect_name = None

        self.inited = False
        self._accept_range = False

        self._started = False
        self._closed = False

        self._task_num = 0
        self._resume = Event()  # 仅内部使用
        self._resume.set()

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
    def length(self):
        return self._contect_length

    @property
    def accept_range(self):
        return self._accept_range

    @property
    def task_num(self):
        return len(self.task_group._tasks)

    @property
    def control_end(
        self,
    ):  # 兼容层，便于子类在不修改pre_divition,re_divition的情况下修改
        return self._stop


    def pre_divition(self, block_num):
        """预分割任务,创建指定数量的任务,并启动,已经移动到init中"""
        return
        if self._start > self.control_end:
            raise RuntimeError
        block_size = (self.control_end - self._start) // block_num
        if block_num != 0:
            for i in range(
                self._start + block_size, self.control_end - block_num, block_size
            ):
                self.divition_task(i)

    async def _base_re_divition(self, start, end):
        pass
    
    async def re_divition(self) -> bool:
        """自动在已有的任务中创建一个新连接,成功则返回True"""
        if len(self._block_list) == 0:
            return False
        max_remain = 0
        for block in self._block_list:
            if block.process > self.control_end:
                break

            if block.running:
                if (block.stop - block.process) // 2 > max_remain:
                    max_remain = (
                        min(block.stop, self.control_end) - block.process
                    ) // 2
                    max_block = block

            else:
                if block.stop - block.process > max_remain:
                    if block.process < self.control_end:
                        max_remain = block.stop - block.process
                        max_block = block

        if max_block.running:
            # 构建新块
            if max_remain >= self:
                self.divition_task((max_block.process + max_block.stop) // 2)
                return True
            return False
        else:
            # 启动已有分块
            self.task_group.create_task(self.download(block))
            return True

    def divition_task(
        self,
        start_pos: int,
    ):  # end_pos:int|None = None):
        """自动根据开始位置创建新任务,底层API"""
        if len(self._block_list) > 0 and start_pos < self._block_list[-1].stop:
            match = False
            for block in self._block_list:
                if block.process < start_pos < block.stop:
                    match = True
                    task_block = Block(start_pos, block.stop, True)  # 分割
                    block.stop = start_pos
                    self._block_list.insert(self._block_list.index(block) + 1, task_block)
                    break
            if not match:
                raise Exception("重复下载")
        else:
            task_block = Block(start_pos, self._contect_length, True)
            self._block_list.append(task_block)
        self.task_group.create_task(self.download(task_block))

    def _init(self, res: httpx.Response):
        """统一的初始化步骤,包括第一次成功连接后初始化下载参数,并创建更多任务,不应该被重写"""
        assert not self.inited
        self.inited = True
        self._headers = res.headers
        self._accept_range = (
            res.headers.get("accept-ranges") == "bytes"
            or res.status_code == httpx.codes.PARTIAL_CONTENT
        )
        if (
            "content-range" in res.headers
            and (size := res.headers["content-range"].split("/")[-1]) != "*"
        ):
            # 标准长度获取
            self._contect_length = int(size)
        elif (
            "content-length" in res.headers
            and res.headers.get("content-length", "identity") == "identity"
        ):
            # 仅适用于无压缩数据，http2可能不返回此报头
            self._contect_length = int(res.headers["content-length"])
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
            print("")

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

        if self.accept_range:
            block_num = self.pre_divition_num
            if self._start > self.control_end:
                raise RuntimeError
            block_size = (self.control_end - self._start) // block_num
            if block_num != 0:
                for i in range(
                    self._start + block_size, self.control_end - block_num, block_size
                ):
                    self.divition_task(i)

    @abstractmethod
    async def _stream_base(self, block: Block):  # 只在基类中重载
        """基础流式获取生成器,会修改block处理截断和网络错误,第一个创建的任务会自动执行下载初始化"""
        await self._resume.wait()
        headers = {"Range": f"bytes={block.process}-"}
        async with client.stream("GET", self.url, headers=headers) as response:
            if response.status_code == 416:
                raise NotSatisRangeError
            response.raise_for_status()

            if not self.inited:
                self._init(response)

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
                await self._resume.wait()

    @abstractmethod
    async def stream(self, block: Block):
        """NotImplemented"""
        raise NotImplementedError
        async for chunk in self._stream_base(block):
            pass

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
        raise NotImplementedError

    async def main(self):
        try:
            async with self.task_group:
                await self.start_coro()
                self.divition_task(self._start)  # 启动第一个任务，会自动执行初始化
                deamon_task = asyncio.create_task(self.deamon())

        except asyncio.CancelledError:
            await self.cancel_coro()

        finally:
            deamon_task.cancel()
            await self.client.aclose()
            self._closed = True
            await self.close_coro()

    async def aclose(self):
        """断开所有连接"""
        return
        self.main_task.cancel()
        await self.main_task

    @abstractmethod
    async def download(self, block: Block):
        """统一的下载任务处理器,会修改block状态,不应该被重写"""
        if block.running:
            return
        block.running = True
        self._task_num += 1

        try:
            self.stream(block)
        except asyncio.CancelledError:
            # 取消时不调用re_divition
            pass

        except Exception:
            await self.re_divition()

        else:
            await self.re_divition()
            self._block_list.remove(block)
        finally:
            self._task_num -= 1
            block.running = False


class AllBase(DownloadBase, ABC):
    """一次性获取所有内容"""

    def __init__(self, url, start: int = 0, stop: int | Inf = Inf()) -> None:
        super().__init__(url, start, stop)

    def pause(self):
        self._resume.clear()

    def unpause(self):
        self._resume.set()

    def run(self):
        """启动下载"""
        asyncio.run(self.main())


class StreamBase(DownloadBase, ABC):
    """基本流式控制策略，没有缓冲大小限制"""

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

    async def _stream_base(self, block: Block):
        async for chunk in super()._stream_base(block):
            yield chunk
            if block.process < self.next_iter_position <= block.process + len(chunk):
                self.iter_now.set()

    async def aiter(self):
        """异步迭代器"""
        while self.iter_process < self._stop:
            if (
                len(self._block_list) != 0
                and self.iter_process + self._iter_step > self._block_list[0].process
            ):
                self.next_iter_position = self.iter_process + self._iter_step
                self.iter_now.clear()
                await self.iter_now.wait()
            yield
    
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
                self.iter_now.clear()
                if not self._loop.is_running():
                    self._loop.run_until_complete(self.iter_now.wait())
            yield

    


class BufferBase(StreamBase):
    """有缓冲大小限制的基本策略"""

    def __init__(self, *arg, step, buffering=16 * MB) -> None:
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
        """返回缓存中已下载的内容占比"""
        return (self._process + self._start - self._iter_process) / self._buffering

    @StreamBase.iter_process.setter
    def iter_process(self, value):
        self._iter_process = value
        self._buffer_end = self._iter_process + self._buffering  ###

    async def _stream_base(self, block: Block):
        for chunk in super()._stream_base(block):
            size = len(chunk)
            if block.process + size > self._buffer_end:
                self.next_download_position = block.process + size
                self.download_now.clear()
                await self.download_now.wait()
            yield chunk

    async def download(self, block: Block):
        await super().download(block)
        await self.re_divition()

    async def re_divition(self):
        while not super().re_divition():
            await self.download_now.wait()

    async def aiter(self):
        for i in super().aiter():
            yield
            if self._iter_process >= self.next_download_position:
                self.download_now.set()


class FileBase(DownloadBase, ABC):
    """写入(异步）文件策略"""

    def __init__(
        self,
        url,
        start: int = 0,
        stop: int | Inf = Inf(),
        path: Path = Path(),
        name=None,
    ) -> None:
        super().__init__(url, start, stop)
        self.path = path
        self.file_name = name

    async def _start(self):
        await super()._start()
        self.aiofile = await aiofiles.open(self.file_name, "w+b")  # 会清除为空文件
        self.file_lock = Lock()

    async def restart(self, path: Path):
        self.aiofile = await aiofiles.open(path, "+ab")


class TempFileBase(DownloadBase, ABC):
    """使用（异步）临时文件策略"""

    async def _start(self):
        await super()._start()
        self.tempfile = await aiofiles.tempfile.TemporaryFile("w+b")
        self.file_lock = Lock()

    async def aclose(self):
        await super().aclose()
        await self.tempfile.close()


class BytesBase(DownloadBase, ABC):
    """使用内存策略"""

    def __init__(self, url, start: int = 0, stop: int | Inf = Inf()):
        super().__init__(url, start, stop)
        self._context = bytearray()


class IterBytes(StreamBase, TempFileBase):
    """在内存中迭代"""

    async def aiter(self):
        for i in super().aiter():
            yield


class IterFile(StreamBase, BytesBase):
    """在文件中迭代"""

    async def aiter(self):
        async for i in super().aiter():
            yield


class ByteBuffer(BufferBase):
    """用内存缓冲"""

    async def _stream_base(self, block: Block, /):
        async for chunk in super()._stream_base(block):
            size = len(chunk)
            assert size < self._buffering
            off = block.process % self._buffering
            if off + size <= self._buffering:
                self._buffer[off : off + size] = chunk
            else:
                self._buffer[off:] = chunk[: off + size - self._buffering]
                self._buffer[off + size - self._buffering] = chunk[
                    off + size - self._buffering :
                ]

    async def __anext__(self):
        await super().__anext__()
        off = self._iter_process % self._buffering
        return self._buffer[off]

    async def _start(self):
        await super()._start()
        self._buffer = bytearray()

    async def aclose(self):
        await super().aclose()
        self._buffer = bytearray()

    async def aiter(self):
        async for i in super().aiter():
            off = self._iter_process % self._buffering
            yield self._buffer[off]


class fileBuffer(BufferBase, TempFileBase):
    """用临时文件缓冲"""

    async def _stream_base(self, block: Block, /):
        async for chunk in super()._stream_base(block):
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
                    await self.tempfile.write(chunk[: off + size - self._buffering])
                    await self.tempfile.seek(0)
                    await self.tempfile.write(chunk[off + size - self._buffering :])

    async def __anext__(self):
        await super().__anext__()
        off = self._iter_process % self._buffering
        size = self._block_list[-1] - self._iter_process
        async with self.file_lock:
            await self.tempfile.seek(off)
            return await self.tempfile.read(self._iter_step)

    async def _start(self):
        await super()._start()
        self.tempfile = await aiofiles.tempfile.TemporaryFile("w+b")
        self.file_lock = Lock()

    async def aclose(self):
        await super().aclose()
        await self.tempfile.close()

    async def aiter(self):
        for i in super().aiter():
            off = self._iter_process % self._buffering
            async with self.file_lock:
                await self.tempfile.seek(off)
                return await self.tempfile.read(self._iter_step)


class AllBytes(AllBase, BytesBase):
    """下载所有内容并保存在内存中"""

    async def _wait(self):
        await super()._wait()
        return self._context

    async def _stream_base(self, block: Block):
        async for chunk in super()._stream_base(block):
            size = len(chunk)
            self._context[block.process : block.process + size] = chunk


class AllFile(AllBase, FileBase):
    """下载所有内容并保存在文件中"""

    def __init__(self, url, start: int = 0, stop: int | Inf = Inf()) -> None:
        super().__init__(url, start, stop)
        self.path = Path() / self.file_name

    async def _wait(self):
        await super()._wait()
        return self.path

    async def reload(self, path: Path):
        pass

    async def _stream_base(self, block: Block):
        async for chunk in super()._stream_base(block):
            async with self.file_lock:
                await self.aiofile.seek(block.process)
                await self.aiofile.write(chunk)


class StreamBytes(AllBytes, StreamBase):
    pass


class StreamFile(AllFile, StreamBase):
    """无文件缓存限制的迭代获取"""

    async def __anext__(self):
        super().__anext__()
        async with self.file_lock:
            await self.aiofile.seek(self._iter_process)
            return await self.aiofile.read(self._iter_step)
