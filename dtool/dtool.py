import asyncio, httpx, aiofiles
import enum
from pathlib import Path
from asyncio import Event, Lock
from abc import ABC, abstractmethod
from pathlib import Path
from .speedlimit import Monitor
from .models import Inf,SpeedInfo, SpeedRecoder,ResponseHander, UnKonwnSize
from ._exception import NotAcceptRangError, NotSatisRangeError

client = httpx.AsyncClient(limits=httpx.Limits())

B = 1
KB = 1024
MB = 1048576
GB = 1073741824
TB = 1099511627776

class Block:
    __slots__ = ("start", "process", "stop", "_task")

    def __init__(
        self, process: int = 0, end_pos: int | Inf = Inf()) -> None:
        self.start = process
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
        return (self.start, self.process, self.stop)

    def __setstate__(self, state: tuple):
        self.start, self.process, self.stop = state


class DownloadBase(ABC):
    """基本控制策略 处理各种基本属性"""

    def __init__(self, url, task_num = 16, chunk_size = None, blocks:None|list[Block] = None, auto = True, max_remain = MB):

        self.client = httpx.AsyncClient(limits=httpx.Limits())
        self.url = url
        self.chunk_size = chunk_size
        self.task_group = asyncio.TaskGroup()
        self.inited = asyncio.Event()
        
        self.max_task_num = task_num
        self.auto = auto
        self.max_remain = max_remain

        self._accept_range = False
        self._contect_length: int | Inf = Inf()
        self._contect_name = None

        self._task_num = 0
        self._stop_divition_task = False
        self._resume = Event()
        self._resume.set()
        self._limit = Monitor()
        self._stop = Inf()
        self._process = 0

        if blocks is None:
            self._block_list = [Block()]
        self.set_process()

    def set_process(self):
        if self._contect_length != UnKonwnSize and self._stop == UnKonwnSize:
            self._stop = self._contect_length
            self._block_list[-1].stop = self._stop

        process = 0
        stop = 0
        if self._block_list[-1].stop == UnKonwnSize:
            self._stop = Inf()
            for i in self._block_list:
                process += i.process - i.start
        else:
            for i in self._block_list:
                process += i.process - i.start
                stop += i.stop - i.process
            self._stop = stop
        self._process = process


    def cancel_one_task(self , max_remain = MB):
        """取消一个最多剩余的任务"""
        match = False
        max_block_remain = 0
        for block in self._block_list:
            if block.running and block.stop - block.process > max_block_remain:
                match = True
                max_block_remain = block.stop - block.process
                max_block = block
                return
            
        if match and max_block_remain > max_remain:
            max_block.cancel_task()

    async def on_task_exit(self):
        """任务退出回调"""
        pass

    def start_block(self, block:Block):
        block.task = self.task_group.create_task(self.download(block))
        self._task_num += 1

    async def _init(self, hander :ResponseHander):
        """统一的初始化步骤,包括第一次成功连接后初始化下载参数,并创建更多任务,不应该被重写"""
        self._contect_length = hander.get_length()
        self._contect_name = hander.get_filename()
        if self._contect_length != UnKonwnSize:
            self._accept_range = hander.get_accept_ranges()
        else:
            self._accept_range = False
        if not self._accept_range:
            self.max_task_num = 1
        self.set_process()

        await self._init_cache()

    
    async def stream(self, block: Block):  # 只在基类中重载
        """基础流式获取生成器,会修改block处理截断和网络错误,第一个创建的任务会自动执行下载初始化,决定如何处理数据"""
        await self._resume.wait()
        headers = {"Range": f"bytes={block.process}-"}
        async with client.stream("GET", self.url, headers=headers) as response:

            hander = ResponseHander(response)
            hander.check_response()
            if not self.inited.is_set():
                await self._init(hander)
                self.inited.set()

            async for chunk in response.aiter_raw(chunk_size = self.chunk_size):
                len_chunk = len(chunk)
                await self._limit.update(len_chunk)
                if block.stop != UnKonwnSize and block.process + len_chunk < block.stop:
                    await self._handing_chunk(block, chunk, len_chunk)
                    self._process += len_chunk
                    block.process += len_chunk
                else:
                    len_chunk = block.stop - block.process
                    await self._handing_chunk(block, chunk[: len_chunk], len_chunk)
                    self._process += len_chunk
                    block.process += len_chunk
                    break
                await self._resume.wait()

            if block.stop is Inf:#解决大小未知的情况
                block.stop = block.process
                self._contect_length = block.stop
                self.set_process()
    
    async def _handing_chunk(self, block:Block, chunk:bytes, chunk_size:int):
        await self._write_cache(block, chunk, chunk_size)

    @abstractmethod
    async def _init_cache(self):
        raise NotImplementedError

    @abstractmethod
    async def _write_cache(self, block:Block, chunk:bytes, chunk_size:int):
        raise NotImplementedError

    @abstractmethod
    async def _read_cache(self, process: int, size: int) -> bytes:
        '''仅在StreamBase及其子类中会被调用,不负责截断，不保证内容是否合法'''
        raise NotImplementedError
    
    @abstractmethod
    async def _close_cache(self):
        raise NotImplementedError

    async def main(self):
        """主函数，负责启动异步任务和处理错误."""
        try:
            block = Block()
            self._block_list = [block]
            async with self.task_group as tg:
                self.start_block(block)
                await self.inited.wait()
                print(f"Start download {self._contect_name}({self._contect_length}\tresumable:{self._accept_range})")
                deamo = self.deamon_auto() if self.auto  else self.deamon_default()
                tg.create_task(deamo)

        except asyncio.CancelledError:
            pass

        finally:
            await self.client.aclose()
            await self._close_cache()

    def divition_task(self, times:int = 1):
        '''相当于运行times次divition_task,但效果更好。在只有一个worker时相当于__clacDivisionalWorker'''
        count:dict[Block,int] = {}
        for block in self._block_list:
            count[block] = 1 if block.running else 0
        
        for i in range(times):#查找分割times次的最优解
            maxblock_remain = 0
            maxblock = None
            for block in self._block_list:
                if (remain := ( block.stop - block.process ) / ( count[block] + 1 )) > maxblock_remain:
                    maxblock_remain = remain
                    maxblock = block

            if maxblock_remain < self.max_remain:
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
        """auto control num of task strategy"""
        # 初始化变量
        print("deamp_auto start")
        recorder = SpeedRecoder(self._process)
        threshold = 0.1 # 判断阈值
        accuracy = 1  # 判断精度

        max_speed_per_connect = 1  # 防止除以0

        info = SpeedInfo()
        info_cache = SpeedInfo()
        task_num_cache = task_num = 0

        while self._process < self._stop:
            if task_num != self._task_num:#更新taskNum， formerTaskNum，formerInfo，重置recorder
                task_num_cache = task_num
                task_num = self._task_num
                info_cache = info

                recorder.reset(self._process)

            elif recorder.flash(self._process).time > 60: #超时重置
                recorder.reset(self._process)

            else:
                info = recorder.flash(self._process) #更新info
                if self._task_num > 0:#更新speedPerConnect，maxSpeedPerConnect
                    speed_per_connect = info.speed / self._task_num
                    if speed_per_connect > max_speed_per_connect:
                        max_speed_per_connect = speed_per_connect
                    
                speed_delta_per_new_thread = (info.speed - info_cache.speed) / (task_num - task_num_cache)# 平均速度增量
                offset = (1 / info.time) * accuracy#误差补偿偏移
                efficiency = speed_delta_per_new_thread / max_speed_per_connect# 线程效率
                print(f"speed:{info.speed:.2f}B/s,task_num:{self._task_num},speed_per_connect:{speed_per_connect:.2f}B/s,max_speed_per_connect:{max_speed_per_connect:.2f}B/s,speed_delta_per_new_thread:{speed_delta_per_new_thread:.2f}B/s,offset:{offset:.2f}B/s,efficiency:{efficiency:.2f}")
                if efficiency >= threshold + offset:
                    if self._task_num  < self.max_task_num:
                        self.divition_task()#create new task

                    elif self._task_num > self.max_task_num:
                        self.cancel_one_task()

                if self._task_num == 0 and self._process < self._contect_length:
                    self.divition_task()#立即启动最后一个线程

            await asyncio.sleep(check_time)

    async def deamon_default(self, check_time = 1):
        '''keep_max_task_num strategy'''
        while self._process < self._stop:
            await asyncio.sleep(check_time)
            if self._task_num < self.max_task_num:
                self.divition_task(self.max_task_num - self._task_num)

            elif self._task_num > self.max_task_num:
                        self.cancel_one_task()

    async def download(self, block: Block):
        """统一的下载任务处理器,会修改block状态,不应该被重写"""
        try:
            await self.stream(block)
        except NotAcceptRangError:
            pass

        except Exception as e:
            #Exception 不包括CancelledError
            pass
        else:
            pass

        finally:
            self._task_num -= 1


class StreamBase(DownloadBase):
    """基本流式控制策略，没有缓冲大小限制"""

    def __init__(self, url, task_num = 16, chunk_size = None, blocks:None|list[Block] = None, start = 0, step = 16 * KB) -> None:
        super().__init__(url,task_num, chunk_size, blocks=blocks)
        self.iterable = Event()
        self._iter_process = start
        self._iter_step = step
        self.next_iterable_check_point = self._iter_process + self._iter_step
        

    async def _handing_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        await self._write_cache(block, chunk, chunk_size)
        if block.process < self.next_iterable_check_point <= block.process + chunk_size:
            self.iterable.set()

    async def __aenter__(self):
        self.main_task = asyncio.create_task(self.main())
        await self.inited.wait()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.main_task.cancel()
        return False

    async def __aiter__(self):
        """异步迭代器, 负责截断，保证内容是否合法'''"""
        main_task = asyncio.create_task(self.main())
        while self._iter_process < self._stop:

            if len(self._block_list) > 0 and  self._iter_process + self._iter_step > self._block_list[0].process:
                self.next_iterable_check_point = self._iter_process + self._iter_step
                self.iterable.clear()
                await self.iterable.wait()

            chunk = await self._read_cache(self._iter_process, self._iter_step)

            if len(chunk) + self._iter_process > self._stop:
                chunk = chunk[: self._stop - self._iter_process]
            self._iter_process += len(chunk)
            yield chunk
        print("download end")
        await main_task


class BufferBase(StreamBase):
    """有缓冲大小限制的基本策略"""

    def __init__(self, *arg, buffering=16 * MB) -> None:
        super().__init__(*arg)
        self.downloadable = Event()
        self.next_downloadable_check_point = self._iter_process
        self._buffering = buffering
        self._buffer_end = self._iter_process + buffering
        if self._block_list[-1].process > self._iter_process + buffering:
            raise ValueError

    async def _handing_chunk(self, block: Block, chunk: bytes, chunk_size: int):
        if block.process > self._iter_process + self._buffering:
            block.cancel_task()

        if block.process + chunk_size > self._iter_process + self._buffering:#检查下一次写入数据会不会超出缓冲区
            self.next_downloadable_check_point = block.process + chunk_size - self._buffering
            self.downloadable.clear()
            await self.downloadable.wait()

        await StreamBase._handing_chunk(self, block, chunk, chunk_size)


    def divition_task(self, times: int = 1):
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
            self._buffer_end = self._iter_process + len(chunk)
            yield chunk
            if self._iter_process >= self.next_downloadable_check_point:
                self.downloadable.set()


class CircleBufferBase(BufferBase):
    '''循环队列缓冲，需要检查缓冲区长度是否符合要求'''
    def __init__(self, *arg) -> None:
        BufferBase.__init__(self, *arg)
        if self._block_list[-1].process > self._iter_process + self._buffering:
            raise ValueError


class FileBase(DownloadBase):
    """写入(异步）文件策略"""

    def __init__(self, url, file_name :str|None= None,path:None|Path = None, task_num = 16, chunk_size = None, blocks:None|list[Block] = None) -> None:
        super().__init__(url,task_num, chunk_size, blocks=blocks)
        self.file_name = file_name
        self.path = path
        self.file_lock = Lock()

    async def _init_cache(self):
        if self.path is None:
            self.path = Path.cwd()

        if self.path.is_dir():
            if self.file_name is not None:
                self.dest = self.path / self.file_name
            else:
                self.dest = self.path / self._contect_name
        elif self.path.is_file():
            self.dest = self.path
        else:
            raise ValueError("path is set but not a exists file or directory")
        self.aiofile = await aiofiles.open(self.dest, "a+b")

    async def _write_cache(self, block: Block, chunk: bytes, chunk_size: int):
        async with self.file_lock:
            await self.aiofile.seek(block.process)
            await self.aiofile.write(chunk)

    async def _read_cache(self, process: int, step: int):
        async with self.file_lock:
            await self.aiofile.seek(process)
            return await self.aiofile.read(step)

    async def _close_cache(self):
        await self.aiofile.close()

class TempFileBase(DownloadBase):
    """使用（异步）临时文件策略"""

    async def _init_cache(self):
        self.tempfile = await aiofiles.tempfile.TemporaryFile("a+b")
        self.file_lock = Lock()

    async def _write_cache(self, block: Block, chunk: bytes, chunk_size: int):
        async with self.file_lock:
            await self.tempfile.seek(block.process)  
            await self.tempfile.write(chunk)

    async def _read_cache(self, process: int, step: int):
        async with self.file_lock:
            await self.tempfile.seek(process)
            return await self.tempfile.read(step)
    
    async def _close_cache(self):
        await self.tempfile.close()


class BytesBase(DownloadBase):
    """使用内存策略"""

    async def _init_cache(self):
        if self._contect_length != UnKonwnSize:
            self._context = bytearray(self._contect_length)
        else:
            self._context = bytearray()

    async def _write_cache(self, block: Block, chunk: bytes, chunk_size: int):
        self._context[block.process : block.process + chunk_size] = chunk

    async def _read_cache(self, process: int, step: int):
        return self._context[process : process + step]

    async def _close_cache(self):
        pass


class ByteBuffer(CircleBufferBase):
    """用内存缓冲"""

    async def _write_cache(self, block: Block, chunk: bytes, chunk_size: int):
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

    async def _init_cache(self):
        self._buffer = bytearray()

    async def _read_cache(self, process:int, step:int):
        off = process % self._buffering
        if off + step <= self._buffering:
            c = self._buffer[off : off + step]
        else:
                c = self._buffer[off : ]
                c += self._buffer[ : off + step - self._buffering]
        if 0 < self._stop - process < step:
            c = c[:self._stop - process]
        return c

    async def _close_cache(self):
        self._buffer = bytearray()


class FileBuffer(CircleBufferBase, TempFileBase):
    """用临时文件缓冲"""
    async def _init_cache(self):
        self.tempfile = await aiofiles.tempfile.TemporaryFile("w+b")
        self.file_lock = Lock()
    
    async def _write_cache(self, block: Block, chunk: bytes, chunk_size: int):
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

    async def _read_cache(self, process:int, step:int):
        off = process % self._buffering
        if off + step <= self._buffering:
            async with self.file_lock:
                await self.tempfile.seek(off)
                chunk = await self.tempfile.read(step)
        else:
            async with self.file_lock:
                await self.tempfile.seek(off)
                chunk = await self.tempfile.read()
                await self.tempfile.seek(0)
                chunk = chunk + await self.tempfile.read(off + step - self._buffering)
        if 0 < self._stop - process < step:
            chunk = chunk[:self._stop - process]
        return chunk

    async def _close_cache(self):
        pass



class BlockBytes(StreamBase):

    def __init__(self, *arg, step, buffering=16 * MB) -> None:
        super().__init__(*arg, step=step, buffering=buffering)
        self._buffers = {block:bytearray() for block in self._block_list}
        self.buffer = bytearray()
        raise NotImplementedError
    
    async def _init_cache(self):
        pass

    def start_block(self, block):
        super().start_block(block)
        self._buffers[block] = bytearray()

    async def _write_cache(self, block: Block, chunk: bytes, chunk_size: int):
        self._buffers[block] += chunk

    async def on_task_done(self):
        pass

    async def download(self, block):
        try:
            await self.stream(block)
        except Exception as e:
            pass
        else:
            chunk = self._buffers.pop(block)
            i = self._block_list.index(block) + 1
            if i < len(self._block_list):
                self._buffers[self._block_list[i]] = chunk + self._buffers[self._block_list[i]]
            self._block_list.remove(block)
            
        finally:
            self._task_num -= 1

    async def _read_cache(self, process, step):
        for block in self._block_list:
            if block.process <= process < block.stop:
                off = process - block.process
        raise NotImplementedError

