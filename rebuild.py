import asyncio, httpx, aiofiles

from taskcoordinator import TaskCoordinator
import functools
#from models import Block
import typing
from contextlib import asynccontextmanager
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

class Block:
    __slots__ = ('process','end','running')
    def __init__(self, process:int, end_pos:int|None = None, running:bool = False ,) -> None:
        if end_pos is None:
            end_pos = models.Inf()
        self.process = process
        self.end = end_pos
        self.running = running
    def __str__(self) -> str:
        return f'{self.process}-{self.end}'

    def __getstate__(self):
        state = {slot: getattr(self, slot) for slot in self.__slots__ if slot != 'running'}
        return state
    
    def __setstate__(self, state:dict):
        for key, value in state.items():
            setattr(self, key, value)
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

    def __init__(self, url) -> None:
        self.client = httpx.AsyncClient(limits=httpx.Limits(),)
        self.url = url
        self.block_list:list[Block] = []
        #self.alive = False
        self._task_group = None

        self.inited = False
        self.init_prepare = TaskCoordinator()
        self.headers = None
        self.file_size = 0
        self.accept_range = None

        self.process = 0

        #self.task = asyncio.create_task(self.main)
        
    @property
    def task_num(self):
        #self.task_group.
        return len(self.task_group._tasks)
    
    @property
    def task_group(self):
        if self._task_group is None or self._task_group._exiting == True:
            self._task_group = asyncio.TaskGroup()
        return self._task_group
    

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
                    self.task_group.create_task(self.stream(new_block))
                    break
            if not match:
                raise Exception('重复下载')
        else:
            new_block = Block(start_pos, self.file_size, True)
            self.block_list.append(new_block)
        self.task_group.create_task(self.stream(new_block))
    
    def _handing_info(self, res:httpx.Response):
        self.saved_info = True
        self.accept_range = 'accept-ranges' in res.headers and res.headers['accept-ranges'] == 'bytes' or res.status_code == httpx.codes.PARTIAL_CONTENT
        if 'content-range' in res.headers and (size := res.headers['content-range'].split('/')[-1]) != '*' :
            #标准长度获取
            self.file_size = int(size)
        elif 'content-length' in res.headers and ( 'content-encoding' not in res.headers or res.headers['content-encoding'] == 'identity' ):
            #仅适用于无压缩数据，http2可能不返回此报头
            self.file_size = int(res.headers['content-length'])
        else:
            self.file_size = models.Inf()
            self.accept_range = False
            if self.accept_range:
                #允许续传，但无法获得文件长度，所以发送res的请求时headers应添加range: bytes=0-不然服务器不会返回'content-range'
                self.accept_range = False
                raise RuntimeWarning()
        self.block_list[-1].end = self.file_size

    def _handing_name(self, res:httpx.Response):
        httpx.URL
        self.file_name = str(res.url).split('/')[-1]

    async def get_info(self):
        res = httpx.head(self.url, headers = {"Range": f"bytes=0-"})
        self._handing_info(res)

    def re_divition_task(self):
        assert self.accept_range  #only accept_range
        raise NotImplementedError
    
    async def main(self, first_connect_pos = 0, block = None):
        if block is None:
            block = Block(0,)
        self.cut_block
        async with asyncio.TaskGroup() as self.task_group:
            self.cut_block(first_connect_pos)
            async with self.init_prepare as res:
                self._handing_info(res)

    async def __aenter__(self):
        pass
    
    async def __aexit__(self, exv, ext, tb):
        pass
    
    def __call__(self):
        pass
    async def init(self, ):
        self.main_task = asyncio.create_task(self.main())

    async def close(self, ):
        self.main_task.cancel()
    async def __await__(self):
        await self.main_task



    async def stream(self, block:Block):
        block.running = True
        headers = {"Range": f"bytes={block.process}-{self.file_size-1}"}

        try:
            async with client.stream('GET',self.url,headers = headers) as response:
                response.raise_for_status()
                if not self.saved_info:
                    #self.headers = response.headers
                    await self.init_prepare.unlock(response)
                    if not self.accept_range and block.process != 0:
                        pass
                len_chunk = 16*KB
                async for chunk in response.aiter_raw(16384):
                    len_chunk = 16834
                    if block.process + len_chunk < block.end:
                        yield chunk
                        self.process += len_chunk
                        block.process += len_chunk
                    else:
                        yield chunk[: block.end - block.process]
                        self.process += block.end - block.process
                        block.process = block.end
                        break
        except httpx._exceptions.HTTPStatusError:
            if response.status_code == httpx.codes.REQUESTED_RANGE_NOT_SATISFIABLE:
                pass
        except httpx._exceptions.HTTPError:
            pass
        except:
            block.running = False
        else:
            self.block_list.remove(block)
        finally:
            self.re_divition_task()


            

    async def download(self, response:httpx.Response, block:Block):
        len_chunk = 16*KB
        async for chunk in response.aiter_raw(16384):
            len_chunk = 16834
            if block.process + len_chunk < block.end:
                yield chunk
                block.process += len_chunk
            else:
                yield chunk[: block.end - block.process]
                block.process = block.end
                break
    async def download(self, block):
        #stream = self.stream(block)
        async for chunk in self.stream(block):
            pass

    

from models import CircleIo
class WebResouseStream(WebResouse):

    def __init__(self, url, seek = 0, step = KB, buffer_size = 16*MB ) -> None:
        super().__init__(url)
        self._entered = False
        self.process = 0
        self.seek = seek
        self.step = step
        self.buffering = buffer_size
        self._start = seek
        self._end = self._start + buffer_size
        self._io = CircleIo(buffer_size)

        self.wait_download = asyncio.Event()
        self.wait_iter = asyncio.Event()
        self.wait_download.set()
        self.wait_iter.set()
    @property
    def start(self):
        return self._start
    @start.setter
    def setter(self, value):
        self._start = value
        self._end = self._start + self.step
    @property
    def end(self):
        return self._end
    
    async def download(self, response: httpx.Response, block):
        finish = False
        len_chunk = 16*KB
        async for chunk in response.aiter_raw(len_chunk):
            len_chunk = len(chunk)
            #wait iter
            while block.process + len_chunk > self.end:
                self.wait_iter.clear()
                await self.wait_iter.wait()

            #write
            if block.process + len_chunk < block.end:
                self._io.seek(block.process)
                self._io.write(chunk)
                block.process += len_chunk
            else:
                self._io.seek(block.process)
                self._io.write(chunk)
                block.process = block.end
                finish = True
                

            #call iter
            if self.start < block.process + len_chunk or block.process  < self.start + self.step:# or self.block_list[0] == block:
                self.wait_download.set()

            if finish:
                break
    async def download(self, block:Block):
        async for chunk in self.stream(block):
            len_chunk = len(chunk)
            while block.process + len_chunk > self.end:
                self.wait_iter.clear()
                await self.wait_iter.wait()

            self._io.seek(block.process)
            self._io.write(chunk)

            if self.start < block.process + len_chunk or block.process  < self.start + self.step:# or self.block_list[0] == block:
                self.wait_download.set()


    async def __anext__(self):
        assert self._entered 
        #wait download
        while self.start + self.step > self.block_list[0].process:
            self.wait_download.clear()
            await self.wait_download.wait()
        #read
        self._io.seek(self.start)
        self._io.read(self.step)
        self.start += self.step
        #call download
        self.wait_iter.set()

    async def main(self, first_connect=0):
        async with self.task_group:
            pass
        return await super().main(first_connect)
        
    
    def pre_division_task(self,  block_num):
        block_size = self.buffering // block_num
        if block_num != 0:
            for i in range(block_size, self.buffering - block_num, block_size):
                self.cut_block(i)()
        #self.speed_cache.reset(block_num)

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
            if max_remain <= 1*MB:
                return
            max_division = min(max_remain_Block.end, self.seek + self.step)
            start_pos = (max_remain_Block.process + max_division) // 2
            self.cut_block(start_pos)
        else:
            max_remain_Block()

    async def __aenter__(self):
        assert not self._entered
        self.main_task = asyncio.create_task(self.main(0))
        await self.task_group.__aenter__()
        self._entered = True
        return self
    async def __aexit__(self, et, exv, tb):
        self.main_task.cancel()
        self._io = None
        return False
    def __aiter__(self):
        return self
    




class WebResouseAll(WebResouse):
    '''需要确保所有部分下载完成'''
    def __init__(self, url) -> None:
        super().__init__(url)
        self.context = bytearray()
        self.process = 0
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
        block_size = block_size = self.file_size / block_num
        for i in range(1,block_num):
            self.cut_block(i*block_num)
 
    async def download(self, response: httpx.Response, block: Block):
        async for chunk in response.aiter_raw(16384):
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



    





