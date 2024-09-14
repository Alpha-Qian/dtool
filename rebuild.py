import asyncio, httpx, aiofiles
from models import Inf
from taskcoordinator import TaskCoordinator
#from models import Block
import typing
from _config import Range, Config, DEFAULTCONFIG, ALL, SECREAT
from _exception import NotAcceptRangError, NotSatisRangeError
client = httpx.AsyncClient(http2=True)

B = 1
KB = 1024
MB = 1048576
GB = 1073741824
TB = 1099511627776
import enum
enum.Enum
loop = None
def sync_run(coro:typing.Coroutine):
    if not loop:
        loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)



def repr(size):
    if size < KB:
        return f'{size/B:.3}B'
    elif size < MB:
        return f'{size/MB:.3}B'
    elif size < GB:
        return f'{size/GB:.3}B'
    

class ConnectIter:
    pass
class Control():
    def __init__(self) -> None:
        self.tasks:list[WebResouse] = []
        self.contr :list[models.SpeedCacher] = []
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
#
class Block:
    __slots__ = ('process','end','running')
    def __init__(self, process:int, end_pos:int|Inf = Inf, running:bool = True) -> None:
        if end_pos is None:
            end_pos = models.Inf()
        self.process = process
        self.end = end_pos
        self.running = False#running

    def __str__(self) -> str:
        return f'{self.process}-{self.end}'



    def __getstate__(self):
        return (self.process, self.end)
    
    def __setstate__(self, state:tuple):
        self.process, self.end = state
        # 恢复未序列化的属性
        self.running = False

import models
    
class WebResouse():
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
        self.file_size = models.Inf()
        self._accept_range = None

        self._process = 0

        #self.task = asyncio.create_task(self.main)
    @property
    def start(self):
        return self._start
    
    @property
    def stop(self):
        return self._stop

    @property
    def process(self):
        return self._process
    
    @property
    def accept_range(self):
        return self._accept_range
    
    @property
    def task_num(self):
        #self.task_group.
        return len(self.task_group._tasks)
    
    @property
    def control_end(self):#兼容层，便于子类在不修改re_divition的情况下修改redivition改在哪里截止
        return self._stop
    
    #-------------------------实验性内容----------------------------
    def new_monitor(self):
        return models.SpeedMonitor(self)

    def new_task(self, block:Block):
        self.task_group.create_task(self.connect(block))

    def pre_divition(self, block_num, block:Block):
        '''对第一个创建的blcok进行分块'''
        
        block_size = (block.end - block.process) // block_num
        i = self.block_list.index(block)
        for start in range(block_size, self.file_size - block_num, block_size):
            i += 1
            block = Block(start, block.end)
            self.block_list.insert(i,block)
            self.new_task(block)
    def pre_divition(self, block_num, start = 0, end = None):
        '''对第一个创建的blcok进行分块'''
        
        block_size = (block.end - block.process) // block_num
        i = self.block_list.index(block)
        for start in range(block_size, self.file_size - block_num, block_size):
            i += 1
            block = Block(start, block.end)
            self.block_list.insert(i,block)
            self.new_task(block)
    
            

    def re_divition(self):
        '''自动在已有的任务中创建一个新连接'''
        max_remain = 0
        max_block = None
        for block in self.block_list:
            if block.running:
                if (block.end - block.process)//2 > max_remain:
                    max_remain = (block.end - block.process)//2
                    max_block = block
                    
            else:
                if block.end - block.process > max_remain:
                    max_remain = block.end - block.process
                    max_block = block
            
        if max_block.running:
            if max_remain < self.config.remain_size:
                return
            i = self.block_list.index(block)
            self.block_list.insert(i+1, max_block)
            block = Block((max_block.process + max_block.end)//2, max_block.end)
            max_block.end = (max_block.process + max_block.end)//2
            self.new_task(block)
        else:
            self.new_task(block)
        
    def divition_task(self, block:Block):
        block.end

    #-----------------------------------------------------

    def cut_block(self,  start_pos:int, ):#end_pos:int|None = None):
        '''自动根据开始位置创建新任务,底层API'''
        if len(self.block_list) > 0 and start_pos < self.block_list[-1].end:
            for block in self.block_list:
                match = False
                if block.process < start_pos < block.end:
                    match = True
                    new_block = Block(start_pos, block.end, True) #分割
                    block.end = start_pos
                    self.block_list.insert(self.block_list.index(block)+1,new_block)
                    break
            if not match:
                raise Exception('重复下载')
        else:
            new_block = Block(start_pos, self.file_size, True)
            self.block_list.append(new_block)
        self.new_task(new_block)
    
    def _handing_info(self, res:httpx.Response):
        self.inited = True
        self._accept_range = 'accept-ranges' in res.headers and res.headers['accept-ranges'] == 'bytes' or res.status_code == httpx.codes.PARTIAL_CONTENT
        if 'content-range' in res.headers and (size := res.headers['content-range'].split('/')[-1]) != '*' :
            #标准长度获取
            self.file_size = int(size)
        elif 'content-length' in res.headers and ( 'content-encoding' not in res.headers or res.headers['content-encoding'] == 'identity' ):
            #仅适用于无压缩数据，http2可能不返回此报头
            self.file_size = int(res.headers['content-length'])
        else:
            self.file_size = models.Inf()
            self._accept_range = False
            if self._accept_range:
                #允许续传，但无法获得文件长度，所以发送res的请求时headers应添加range: bytes=0-不然服务器不会返回'content-range'
                self._accept_range = False
                raise RuntimeWarning()
        
        if not self._accept_range and self.req_range.force == SECREAT:
            raise NotAcceptRangError
        self.req_range.stop = min(self.req_range.stop, self.file_size)
        self.block_list[-1].end = self.file_size

    def _handing_name(self, res:httpx.Response):
        httpx.URL
        self.file_name = str(res.url).split('/')[-1]

    async def get_info(self):
        res = httpx.head(self.url, headers = {"Range": f"bytes=0-"})
        self._handing_info(res)

    def re_divition_task(self):
        assert self._accept_range  #only accept_range
        raise NotImplementedError
    
    async def main(self, first_connect_pos = 0, block = None):
        if block is None:
            block = Block(0,)
        self.cut_block
        async with asyncio.TaskGroup() as self.task_group:
            self.cut_block(first_connect_pos)
            async with self.init_prepare as res:
                self._handing_info(res)


    async def stream(self, block:Block):
        '''基础网络获取生成器，会修改block处理截断和网络错误'''
        if block.running:
            return
        block.running = True

        headers = {"Range": f"bytes={block.process}-"}
        try:
            async with client.stream('GET',self.url,headers = headers) as response:
                if response.status_code == 416:
                    raise NotSatisRangeError
                response.raise_for_status()

                if not self.inited:
                        #self.headers = response.headers
                    await self.init_prepare.unlock(response)#wait for init
                    block.end = self.file_size

                async for chunk in response.aiter_raw(16*KB):
                    len_chunk = len(chunk)
                    if block.process + len_chunk < block.end:
                        yield chunk
                        self._process += len_chunk
                        block.process += len_chunk
                    else:
                        yield chunk[: block.end - block.process]
                        self._process += block.end - block.process
                        block.process = block.end
                        break
        except httpx.TimeoutException:
            print(f'TimeoutError: {self.url}')
        else:
            self.block_list.remove(block)#不会有事的
        finally:
            block.running = False



    async def download(self, block):
        async for chunk in self.stream(block):
            raise NotImplementedError
        self.re_divition()

    
from models import CircleFuffer
class WebResouseStream(WebResouse):

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

    def pre_division_task(self,  block_num):
        block_size = self._buffering // block_num
        if block_num != 0:
            for i in range(self.iter_process + block_size, self.buffer_end - block_num, block_size):
                self.cut_block(i)
        #self.speed_cache.reset(block_num)
    def re_divition_task(self):
        return super().re_divition_task()

    def re_division_task(self) -> bool:
        '''负载均衡，创建任务并运行'''
        max_remain = 0
        cut_block = True
        for i in self.block_list:
            if not i.running and (i.end - i.process)*2 > max_remain:
                cut_block = False
                max_remain_Block= i
            elif i.end - i.process > max_remain:
                cut_block = True
                max_remain = i.end - i.process
                max_remain_Block= i
        if cut_block:
            while max_remain <= 1*MB:   
                #await self.wait_iter.wait()#<------注意,此时不再资源安全
                return False#失败
            max_division = min(max_remain_Block.end, self.seek + self._step)
            start_pos = (max_remain_Block.process + max_division) // 2
            self.cut_block(start_pos)
            return True
        else:
            max_remain_Block()
            return True
    async def divition_wait(self):
        while not self.re_division_task():
            await self.wait_iter.wait()



    async def download(self, block:Block):
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
            assert block is models.Inf or block.process == block.end
            self.wait_download.set()#结束检测
            while block.process + len_chunk > self.buffer_end:
                self.wait_iter.clear()
                await self.wait_iter.wait()
            



    async def __anext__(self):
        #await self.wait_init.wait()
        #wait download
        if self.iter_process >= self.file_size:
            raise StopAsyncIteration
        if len(self.block_list) != 0 and self.iter_process + self._step > self.block_list[0].process:
            self.wait_download.clear()
            await self.wait_download.wait()#bug:完成后会一直wait

        #read
        self._buffer.seek(self.iter_process)
        if self.iter_process + self._step < self.file_size:
            i = self._buffer.read(self._step)#<-------bug：不会截断
            self.iter_process += self._step
        else:
            i = self._buffer.read(self.file_size - self.iter_process)
            self.iter_process = self.file_size

        #call download
        self.wait_iter.set()
        #if self.block_list[-1]
        return i

    async def __aenter__(self):
        assert not self._entered
        self._entered = True
        self.task_group = await asyncio.TaskGroup().__aenter__()
        self.cut_block(0)
        async with self.init_prepare as res:
            self._handing_info(res)
            self._handing_name(res)
            self.block_list[-1].end = self.file_size
        return self
    
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


asyncio.Task


class WebResouseAll(WebResouse):
    '''需要确保所有部分下载完成'''
    def __init__(self, url) -> None:
        super().__init__(url)
        self.context = bytearray()
        self._process = 0
        self.task = asyncio.create_task(self.main())
    async def __await__(self):
        await self.task
    
    def _handing_info(self, pre_task_num):
        super()._handing_info()
        self.pre_division_task(pre_task_num)
        self.context = bytearray(self.file_size)
    
    def pre_division_task(self,  block_num):
        block_size = self.file_size // block_num
        if block_num != 0:
            for i in range(block_size, self.file_size - block_num, block_size):
                self.cut_block(i)
        return
    async def main(self, first_connect_pos=0, block=None):
        async with asyncio.TaskGroup() as self.task_group:
            pass
    async def download(self,block):
        async for chunk in self.stream(block):
            len_chunk = len(chunk)
            self.context[block.process:block.process + len_chunk] = chunk


class WebResouseFile(WebResouseAll):
    '''需要初始化文件'''

    def __init__(self, url) -> None:
        super().__init__(url)
        self.speed_cache = models.SpeedCacher(self)
    
    def __await__(self):
        return super().__await__()
    
    def _handing_info(self):
        super()._handing_info()
        self.file = aiofiles.open('','w+b')
    
    async def main(self):
        self.cut_block(0)
        async with self.init_prepare:
            self._handing_info()
            self._handing_name()
            self.file_name
            self.file = await aiofiles.open(self.file_name, 'w+b')
        async with asyncio.TaskGroup() as self.task_group:
            pass
    

class WebResouseDownload(WebResouseFile, WebResouseAll):
    

    def re_division_task(self):
        '''负载均衡，创建任务并运行'''
        max_remain = 0
        cut_block = True
        for i in self.block_list:
            if not i.running and (i.end - i.process)*2 > max_remain:
                cut_block = False
                max_remain_Block= i
            elif i.end - i.process > max_remain:
                cut_block = True
                max_remain = i.end - i.process
                max_remain_Block= i
        if cut_block:
            if max_remain <= 1048576: #1MB
                return
            start_pos = (max_remain_Block.process + max_remain_Block.end) // 2
            self.cut_block(start_pos)()
            self.speed_cache.change()
        else:
            max_remain_Block()
            self.speed_cache.change()
    async def main(self):
        self.cut_block(0)
        async with self.init_prepare:
            self._handing_info()
        async with asyncio.TaskGroup() as tg:
            pass

    def _handing_info(self):
        super()._handing_info()
        self.pre_division_task()
    def main(self):
        return super().main()









