import asyncio, httpx, aiofiles
import models
import functools
#from models import Block
import typing
from contextlib import asynccontextmanager
from models import UnaccpetRangeError
client = httpx.AsyncClient()

httpx.Response
B = 1
KB = 1024
MB = 1048576
GB = 1073741824
TB = 1099511627776

loop = None
def sync_run(coro:typing.Awaitable):
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
    

class ConnectBase:
    '基类'
    
    def __init__(self, start, end, mission):
        self.process = start
        self.end = end
        self.mission:WebResouse = mission
        self.running = False
        self()

    async def run(self):
        self.running = True
        mission = self.mission

        if mission.saved_info:
            headers = {"Range": f"bytes={self.process}-{mission.file_size-1}"}
        else:
            headers = dict()
        async with client.stream('GET',mission.url,headers = headers) as response:
            if not mission.saved_info:
                mission.headers = response.headers
                await mission.inited.unlock()
            await self.main(response)

    async def main(self,response:httpx.Response):
        async for chunk in response.aiter_raw(16384):
            len_chunk = 16834
            if self.process + len_chunk < self.end:
                yield chunk
                self.process += len_chunk
            else:
                yield chunk[: self.end - self.process]
                break

        raise NotImplementedError()
    
    def __call__(self):
        self.mission.task_num += 1
        self.running = True
        self.task = asyncio.create_task(self.run())
        self.task.add_done_callback(self.call_back)
        
    def call_back(self,task:asyncio.Task):
        try:
            task.result()
        except httpx._exceptions:
            print('\t\t\t\tHTTPX ERROR')
        else:
            self.mission.block_list.remove(self)
        finally:
            self.running = False
            print(f'callback\t{self.mission.task_num - 1}')
            self.mission.task_num -= 1
            self.mission.call_back()
    async def __await__(self):
        await self.task
asyncio.TaskGroup

class ConnectBuffer(ConnectBase):
    '''有缓存类,用于stream或all'''

    def __init__(self, start, end, web_resouse) -> None:
        super().__init__(start, end, web_resouse)
        self.buffer = bytearray()
        #self.buffer_list :list[bytearray] = []  可能会启用

    async def main(self, response: httpx.Response):
        async for chunk in response.aiter_raw(16384):
            len_chunk = 16834
            if self.process + len_chunk < self.end:
                self.buffer += chunk
                self.process += len_chunk
            else:
                self.buffer += chunk[: self.end - self.process]
                self.process = self.end
                break
    def call_back(self, task: asyncio.Task):
        try:
            task.result()
        except httpx._exceptions:
            print('\t\t\t\tHTTPX ERROR')
        else:
            self.mission.re_division_task()
        finally:
            self.running = False
            print(f'callback\t{self.mission.task_num - 1}')
            self.mission.task_num -= 1
            self.mission.call_back()


class ConnectFile(ConnectBase):
    '''立即异步写入文件，关心整个文件的处理情况'''
    async def main(self, response: httpx.Response):
        mission = self.mission
        async for chunk in response.aiter_raw(16834):   #<--待修改以避免丢弃多余的内容
                len_chunk = 16834
                if self.process + len_chunk < self.end:
                    async with mission.file_lock:
                        await mission.file.seek(self.process)
                        await mission.file.write(chunk)
                    self.process += len_chunk
                    mission.process += len_chunk

                else:
                    check_chunk = chunk[self.end - self.process:]
                    chunk = chunk[: self.end - self.process]
                    len_chunk = self.end - self.process
                    async with mission.file_lock:
                        await mission.file.seek(self.process)
                        await mission.file.write(chunk)
                        self.process = self.end
                        self.mission.process += len_chunk

                        if (i := mission.block_list.index(self) + 1) == len(mission.block_list):
                            await mission.file.truncate()
                        elif self.process + len_chunk < mission.block_list[i].process :
                            i = await mission.file.read(self.process + len_chunk - self.end)#
                            if i == check_chunk:
                                print('校验成功')
                                break
                            else:
                                self.end = mission.block_list[i].process
                                await mission.file.write(check_chunk)
                                mission.process += len(check_chunk)
                                self.process += len(check_chunk)


class ConnectTemp(ConnectFile):
    '''异步写入临时文件，不关心整个文件的处理情况'''

    async def main(self, response: httpx.Response):
        mission = self.mission
        async for chunk in response.aiter_raw(16834):   #<--待修改以避免丢弃多余的内容
            len_chunk = 16834
            if self.process + len_chunk < self.end:
                async with mission.file_lock:
                    await mission.file.seek(self.process)
                    await mission.file.write(chunk)
                self.process += len_chunk
            else:
                async with mission.file_lock:
                    await mission.file.seek(self.process)
                    await mission.file.write(chunk[: self.end - self.process])


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
                if i.get_speed(), max_get)

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

class Block:
    __slots__ = ('process','end','running')
    def __init__(self, process:int, end_pos:int, running:bool = False ,) -> None:
        self.process = process
        self.end = end_pos
        self.running = running

    def __getstate__(self):
        state = {slot: getattr(self, slot) for slot in self.__slots__ if slot != 'running'}
        return state
    
    def __setstate__(self, state:dict):
        for key, value in state.items():
            setattr(self, key, value)
        # 恢复未序列化的属性
        self.running = False


class WebREsouseBase:

class WebResouse(typing.Awaitable, typing.AsyncContextManager):
    '''基类，只关心资源和连接状况，连接'''
    client = client
    def __init__(self, url) -> None:
        self.url = url
        self.block_list:list[Block] = []
        #self.alive = False
        self._task_group = None

        self.inited = False
        self.init_prepare = models.TaskCoordinator()
        self.headers = None
        self.res_size = 0
        self.accept_range = None

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
    
    async def get_info(self):
        self.headers = await self.client.head(self.url)
        self._init()
    
    def cancel(self):
        self.task.cancel()

    async def __await__(self):
        await self.task
    def __getstate__(self):
        attr = ('url',
         'block_list',
         'inited',
         'res_size',
         'accept_range')
        return {i:getattr(self,i) for i in self.__dict__ if i in attr}
    def __setstate__(self,state):
        self.__init__()
        self.__dict__.update(state)
    
    def cut_block(self,  start_pos:int, ):#end_pos:int|None = None):
        '''自动根据开始位置创建新任务,底层API'''
        if len(self.block_list) > 0 and start_pos < self.block_list[-1].end:
            for block in self.block_list:
                if block.process < start_pos < block.end:
                    new_block = Block(start_pos, block.end) #分割
                    block.end = start_pos
                    self.block_list.insert(self.block_list.index(block)+1,new_block)
                    self.task_group.create_task(self.connect(new_block))
                    new_block.running = True
                    return
            raise Exception('重复下载')
        else:
            new_block = Block(start_pos, self.res_size)
            self.block_list.append(new_block)
            self.task_group.create_task(self.connect(new_block))
            new_block.running = True
    
    def _init(self):
        self.saved_info = True
        if 'content-length' in self.headers:
            self.file_size = int(self.headers['content-length'])
            self.accept_range = 'accept-ranges' in self.headers and self.headers['accept-ranges'] == 'bytes'
        else:
            self.file_size = 1
            self.accept_range = False
        self.block_list[-1].end = self.file_size
    
    async def main(self, first_connect_pos = 0):
        self.task = asyncio.current_task()
        async with asyncio.TaskGroup() as self.task_group:
            self.cut_block(first_connect_pos)()
            async with self.init_prepare:
                self._init()

    



    async def connect(self, block:Block):
        block.running = True
        if self.saved_info:
            headers = {"Range": f"bytes={block.process}-{self.file_size-1}"}
        else:
            headers = {}
        try:
            async with client.stream('GET',self.url,headers = headers) as response:
                #response.status_code == httpx.codes.PARTIAL_CONTENT
                if not self.saved_info:
                    self.headers = response.headers
                    await self.init_prepare.unlock()
                    if not self.accept_range and block.process != 0:
                        pass
                await self.download(response, block)
        except:
            block.running = False
        else:
            self.block_list.remove(block)
        finally:
            self.re_divition_task()
    def re_divition_task(self):
        raise NotImplementedError
            

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
    
    async def aclose(self):
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
        async with self.task_group
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
            if max_remain <= 1048576: #1MB
                return
            max_division = min(max_remain_Block.end, self.seek + self.step)
            start_pos = (max_remain_Block.process + max_division) // 2
            self.cut_block(start_pos)
        else:
            max_remain_Block()

    def __aenter__(self):
        assert not self._entered
        self.main_task = asyncio.create_task(self.main(0))
        self.task_group.__aenter__()
        self._entered = True
        return self #models.StreamControl(self.block_list)
    
    def __aexit__(self, et, exv, tb):
        self.main_task.cancel()
    


    
    
    

class WebResouseAll(WebResouse):
    '''需要确保所有部分下载完成'''
    def __init__(self, url) -> None:
        super().__init__(url)
        self.context = bytearray()
        self.process = 0
        self.task = asyncio.create_task(self.main())
    async def __await__(self):
        await self.task
    
    def _init(self, pre_task_num):
        super()._init()
        self.pre_division_task(pre_task_num)
        self.context = bytearray(self.res_size)
    
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
    
    def _init(self):
        super()._init()
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
            self._init()
        async with asyncio.TaskGroup() as tg:

    def _init(self):
        super()._init()
        self.pre_division_task()
    def main(self):
        return super().main()

class WebResouseTemp(WebResouseBuffer, WebResouseFile):

    def __init__(self, url, buffer_size) -> None:
        super().__init__(url, buffer_size)
        self.file = None
    def _init(self):
        super().init()
        self.file = aiofiles.tempfile.TemporaryFile('w+b')
    def close(self):
        return super().close()


    





