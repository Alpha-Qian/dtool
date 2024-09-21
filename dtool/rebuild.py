import asyncio, httpx, aiofiles
import asyncio.mixins
from dtool.models import Inf
from dtool.taskcoordinator import TaskCoordinator
#from models import Block
import typing
from dtool._config import Range, Config, DEFAULTCONFIG, SECREAT
from dtool._exception import NotAcceptRangError, NotSatisRangeError
import time
client = httpx.AsyncClient(http2=True)

B = 1
KB = 1024
MB = 1048576
GB = 1073741824
TB = 1099511627776


class Control():
    def __init__(self) -> None:
        self.tasks:list[DownloadBase] = []
        self.contr :list[dtool.models.SpeedCacher] = []
    def retry(self):
        pass
    async def control(self):
        while 1:
            await asyncio.sleep(0)
            max_get = 0
            for i in self.contr:
                pass
                

    async def __aenter__(self):
        pass
    async def __aexit__(self):
        pass
    def save(self):
        pass
    def get(self):
        pass
    def stream(self):
        pass
typing.AsyncContextManager
asyncio.TaskGroup

class Runner(asyncio.Runner):
    pass

def build_ranges(start = 0, end = ''):
    return {'Ranges':f'bytes ={start}-{end}'}

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

class DownloadBase:
    '''基类，只关心资源和连接状况，连接'''
    
    get_attr = ('url', 'file_size', 'accept_range')

    def __getstate__(self) -> object:
        return {i:self.__dict__[i] for i in self.get_attr}
    
    def __setstate__(self, state):
        self.__init__(None)
        self.__dict__.update(state)

    def __init__(self, url, start:int = 0, stop:int|Inf = Inf(), config:Config = DEFAULTCONFIG) -> None:
        self.client = httpx.AsyncClient(limits=httpx.Limits(),)
        self.config:Range = config
        self.url = url
        self.block_list:list[Block] = []
        
        self._start = start
        self._stop = stop

        self.inited = False
        self.init_prepare = TaskCoordinator()
        self.headers = None
        self._file_size = models.Inf()
        self._accept_range = None

        self._process = 0

        self.unpause_event = asyncio.Event()
        self.unpause_event.set()

        self._entered = False
        self._exited = False

        self.init_event = asyncio.Event()
        self.done_event = asyncio.Event()


        #self.task = asyncio.create_task(self.main)
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
        self.unpause_event.clear()
    
    def unpause(self):
        self.unpause_event.set()
    
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

    def auto_connect(self):
        yield

    def new_monitor(self):
        return models.SpeedMonitor(self)

    def pre_divition(self,  block_num):
        if self._start > self.control_end:
            raise RuntimeError
        block_size = ( self.control_end - self._start ) // block_num
        if block_num != 0:
            for i in range(self._start + block_size, self.control_end - block_num, block_size):
                self.divition_task(i)
        #self.speed_cache.reset(block_num)

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
            if max_remain >= self.config.remain_size:
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

    def _handing_name(self, res:httpx.Response):
        #url = httpx.URL(self.url)
        #self.file_name = url.raw_path
        self.file_name = str(res.url).split('/')[-1]

    async def stream(self, block:Block):
        '''基础网络获取生成器,会修改block处理截断和网络错误'''
        await self.unpause_event.wait()
        headers = {"Range": f"bytes={block.process}-"}
        async with client.stream('GET',self.url,headers = headers) as response:
            if response.status_code == 416:
                raise NotSatisRangeError
            response.raise_for_status()

            if not self.inited:
                #self.headers = response.headers
                await self.init_prepare.unlock(response)#wait for init
                #block.end = self.file_size

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
                await self.unpause_event.wait()

    async def range_stream(self, block:Block):
        raw_block = Block()
        for chunk in self.stream(raw_block):
            size = len(chunk)
            if raw_block.process > block.process:
                block.process = raw_block.process
                yield chunk
            elif size + raw_block.process > block.process:
                yield chunk[block.process - raw_block.process:]
            

    async def download(self, block:Block):
        if block.running:
            return
        block.running = True
        try:
            stream = self.stream(block)
            async for chunk in stream:
                raise NotImplementedError
        except httpx.TimeoutException:
            print(f'TimeoutError: {self.url}')
        except asyncio.CancelledError:
            print('CancelError')
        else:
            self.block_list.remove(block)
            if len(self.block_list) == 0:
                self.done_event.set()
        finally:
            await stream.aclose()
            block.running = False
            self.re_divition()

    
from .models import CircleFuffer
class WebResouseStream(DownloadBase):

    def __init__(self, url, start = 0, stop = Inf, step = 16*KB, buffering = 16*MB ) -> None:
        super().__init__(url, start, stop)
        self._entered = False
        self._step = step
        self._buffering = buffering
        self._buffer_start = start
        self._buffer_end = self._buffer_start + buffering
        self._buffer = CircleFuffer(buffering)

        #self.wait_init = asyncio.Event()
        self.wait_download = asyncio.Event()
        self.wait_iter = asyncio.Event()
        self.wait_download.set()
        self.wait_iter.set()

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


    async def download(self, block:Block):
        try:
            async for chunk in self.stream(block):
                len_chunk = len(chunk)
            #wait iter
                while block.process + len_chunk > self.buffer_end:
                    self.wait_iter.clear()
                    await self.wait_iter.wait()

            #write
                self._buffer.seek(block.process)
                self._buffer.write(chunk)

            #call iter  暂时没有结束检测
                if block == self.block_list[0] and block.process + len_chunk >= self.iter_process + self._step :
                    self.wait_download.set()
            if block == self.block_list[-1]:
                assert block is models.Inf or block.process == block.stop
                self.wait_download.set()#结束检测
                while block.process + len_chunk > self.buffer_end:
                    self.wait_iter.clear()
                    await self.wait_iter.wait()
            self.block_list.remove(block)
        except:
            pass
        finally:
            block.running = False
            await self.divition_wait()
    
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
    
    async def start(self):
        return await super().start()
    
    async def __aexit__(self, et, exv, tb):
        assert self._entered
        for i in self.task_group._tasks:
            i.cancel()
        await self.task_group.__aexit__()# et, exv, tb)
        self._buffer = None
        return False
    
    def __aiter__(self):
        return self
    
    '''new methods  '''
    async def aiter(self):
        return
        await self.__aenter__()
        while len(self.block_list) > 0:
            if self.iter_process + self._step > self.block_list[0].process:
                self.wait_download.clear()
                await self.wait_download.wait()#bug:完成后会一直wait

            #read
            self._buffer.seek(self.iter_process)
            i = self._buffer.read(self._step)
            self.iter_process += self._step

            #call download
            self.wait_iter.set()
            #if self.block_list[-1]
            yield i


class WebResouseAll(DownloadBase):
    '''需要确保所有部分下载完成'''
    def __init__(self, url) -> None:
        super().__init__(url)
        self.context = bytearray()

    @property
    def control_end(self):
        return self._file_size
    
    def _handing_info(self, pre_task_num):
        super()._handing_info()
        self.context = bytearray(self._file_size)

    async def download(self,block):
        try:
            async for chunk in self.stream(block):
                len_chunk = len(chunk)
                self.context[block.process:block.process + len_chunk] = chunk
            self.block_list.remove(block)
        except:
            pass 
        finally:
            block.running = False
            self.re_divition()
            


class WebResouseFile(DownloadBase):
    '''需要初始化文件'''

    def __init__(self, url) -> None:
        super().__init__(url)
        
    
    def __await__(self):
        return super().__await__()
    
    def _handing_info(self):
        super()._handing_info()
        self.file = aiofiles.open('','w+b')
    
    async def start(self):
        self.file = await aiofiles.open('file_name','w+b')
        await super().start()
        

    async def wait(self):
        await self.file.close()
        await super().wait()

class StreamFile(WebResouseFile, WebResouseStream):

    async def __init__(self, url) -> None:
        super().__init__(url)
        self.file = aiofiles
    async def download(self, block: models.Block):
        try:
            stream = self.stream(block)
            for chunk in stream:
                pass

        finally:
            await stream.aclose()
            await self.divition_wait()
    
    async def __anext__(self):
        pass

class StreamBase(DownloadBase):

    def __init__(self, *arg, **kwarg) -> None:
        super().__init__(*arg, **kwarg)
        self.wait_iter = 
    
    async def stream(self, block: models.Block):
        stream = super().stream(block)
        for i in stream:
            size = len(i)
            while block.process + len_chunk > self.buffer_end:
                    self.wait_iter.clear()
                    await self.wait_iter.wait()
            yield i
            if block == self.block_list[0] and block.process + len_chunk >= self.iter_process + self._step :
                    self.wait_download.set()
    async def __anext__(self):
        pass

    async def iter_raw(self):
        pass
            

    def next_iter(self, size):
        ''''''
class FileStream:
    def re_divition(self):
        iter_speed = 0#
        speed_per_thread = speed_now/task_num
        target_pre_thread = int(iter_speed/speed_per_thread) + 1
        remain = 0
        pre_thread = 0
        for i in self.block_list:
            pre_thread += 1
            if pre_thread > target_pre_thread:
                break
            pre_time = remain / (iter_speed - pre_thread * speed_per_thread)
            if i.process + pre_thread * speed_per_thread  < self.block_list[pre_thread]:
                self.divition_task(i.process + pre_thread * speed_per_thread * 0.8)#0.8:提前系数
            remain += i.process - i.starti.process + pre_thread * speed_per_thread
            




    










