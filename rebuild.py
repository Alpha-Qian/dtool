import asyncio, httpx, aiofiles
import models
import functools
from models import Block
import typing
from contextlib import asynccontextmanager
client = httpx.AsyncClient()
def sync(func:function):
    @functools.wraps(func)
    def new_func(*arg ,**kwarg):
        asyncio.get_event_loop
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
        
class ConnectSyncFile(ConnectBase):
    '''同步写入文件，关心整个文件的处理情况'''
    def __init__(self, start, end, mission: DownloadFile):
        raise NotImplementedError
        super().__init__(start, end, mission)

class ConnectSyncTemp(ConnectSyncFile, ConnectBuffer):

    '''同步写入临时文件'''
    def __init__(self, start, end, mission: DownloadFile):
        raise NotImplementedError
        super().__init__(start, end, mission)


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



class WebResouse(typing.Awaitable):
    '''基类，只关心资源和连接状况，连接'''
    client = client
    def __init__(self, url) -> None:
        self.url = url
        self.block_list:list[ConnectBase] = []
        self.alive = False
        self.task_group = None

        self.inited = False
        self.init_prepare = models.TaskCoordinator()
        self.headers = None
        self.res_size = 0
        self.accept_range = None

        self.task = asyncio.create_task(self.main)
        
    @property
    def task_num(self):
        #self.task_group.
        return len(self.task_group._tasks)
    def cancel(self):
        self.task.cancel()
    async def __await__(self) -> asyncio.Generator[asyncio.Any, asyncio.Any, Any]:
        await self.task
    
    def cut_block(self, tg, start_pos:int, end_pos:int|None = None):
        '''自动根据开始位置创建新任务,底层API'''
        if len(self.block_list) > 0 and start_pos < self.block_list[-1].end:
            for block in self.block_list:
                if block.process < start_pos < block.end:
                    new_block = Block(start_pos, block.end) #分割
                    block.end = start_pos
                    self.block_list.insert(self.block_list.index(block)+1,new_block)
                    self.task_group.create_task(self.connect(new_block))
                    return
            raise Exception('重复下载')
            if end_pos is not None:
                new_block = ConnectBase(start_pos, end_pos, self)
                self.block_list
        else:
            new_block = self.new_block(start_pos, self.res_size)
            self.block_list.append(new_block)
            self.task_group.create_task(self.connect(new_block))
    
    def init(self):
        self.saved_info = True
        if 'content-length' in self.headers:
            self.file_size = int(self.headers['content-length'])
            self.accept_range = 'accept-ranges' in self.headers
        else:
            self.file_size = 1
            self.accept_range = False
        self.block_list[-1].end = self.file_size
    
    async def main(self, first_connect_pos = 0):
        self.task = asyncio.current_task()
        async with asyncio.TaskGroup() as self.task_group:
            self.cut_block(first_connect_pos)()
            async with self.init_prepare:
                self.init()

    



    async def connect(self, block:models.Block):
        try:
            block.running = True
            if self.saved_info:
                headers = {"Range": f"bytes={block.process}-{self.file_size-1}"}
            else:
                headers = dict()
            async with client.stream('GET',self.url,headers = headers) as response:
                if not self.saved_info:
                    self.headers = response.headers
                    await self.inited.unlock()
                await self.download(response, block)
        except:
            pass
        finally:
            block.running = False

    async def download(self, response:httpx.Response, block:models.Block):
        async for chunk in response.aiter_raw(16384):
            len_chunk = 16834
            if block.process + len_chunk < block.end:
                yield chunk
                block.process += len_chunk
            else:
                yield chunk[: block.end - block.process]
                block.process = block.end
                break
httpx.AsyncClient.stream

class WebResouseStream(WebResouse):

    def __init__(self, url, seek = 0, step = 1024, buffer_size = -1 ) -> None:
        super().__init__(url)
        self._aborting = False#终止
        self._entered = False
        self.process = 0
        self.seek = seek
        self.step = step
        self.buffering = buffer_size
        self.buffer = bytearray()
        self.wait_download = asyncio.Event()
        self.wait_iter = asyncio.Event()
    
    async def download(self, response: httpx.Response, block):
        finish = False
        async for chunk in response.aiter_raw(16384):
            len_chunk = 16834
            if block.process + len_chunk < block.end:
                block.buffer += chunk
                block.process += len_chunk

            else:
                block.buffer += chunk[: block.end - block.process]
                block.process = block.end
                i = self.block_list.index(block)
                if i + 1 != self.block_list:
                    self.block_list[i+1].buffer = block.buffer+self.block_list[i+1].buffer
                    self.block_list.remove(block)
                finish = True

            if block.process >= self.seek + self.step:
                await self.wait_iter.wait()
            if block.process < self.seek < block.process + len_chunk:
                self.wait_download.set()
            if finish:
                break
    async def main(self, first_connect=0):
        return await super().main(first_connect)
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
        self.task_group.__aenter__()
        self._entered = True
        return self
    
    def __aexit__(self, et, exv, tb):
        for i in self.task_group._tasks:
            i.cancel()
    def aiter(self):
        while 1:
            pass


    
    async def __anext__(self):
        assert self._entered
        #self.block_list[-1].end += self.step
        self.seek += self.step
        self.wait_iter.set()
        block = self.block_list[0]
        if len(self.buffer) >= self.step:
            i = self.buffer[:self.step]
            del self.buffer[:self.step]
            return i
        else:
            self.block_list[0].on_wait = True
            await self.wait_download
            return super().__anext__()

class Streamer:
    def __init__(self, res) -> None:
        self.res = res
        self.stream_fut = None
    async def __anext__(self, res)

class WebResouseAll(WebResouse):
    '''需要确保所有部分下载完成'''
    def __init__(self, url) -> None:
        super().__init__(url)
        self.context = bytearray()
        self.process = 0
    async def __await__(self):
        await super().__await__()
        return self
    
    def init(self, pre_task_num):
        super().init()
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
 
    

        

class WebResouseFile(WebResouseAll):
    '''需要初始化文件'''

    def __init__(self, url) -> None:
        super().__init__(url)
        self.speed_cache = models.SpeedCacher(self)
    
    def __await__(self):
        return super().__await__()
    
    def init(self):
        super().init()
        self.file = aiofiles.open('','w+b')
    
    
class WebResouseDownload(WebResouseFile, WebResouseAll):
    
    async def __await__(self):
        return await super().__await__()

    def re_division_task(self):
        '''负载均衡，创建任务并运行'''
        max_remain = 0
        cut_block = True
        for i in self.block_list:
            if not i.running and (i.end - i.process)*2 > max_remain:
                cut_block = False
                max_remain_Block:DownBlocks = i
            elif i.end - i.process > max_remain:
                cut_block = True
                max_remain = i.end - i.process
                max_remain_Block:DownBlocks = i
        if cut_block:
            if max_remain <= 1048576: #1MB
                return
            start_pos = (max_remain_Block.process + max_remain_Block.end) // 2
            self.cut_block(start_pos)()
            self.speed_cache.change()
        else:
            max_remain_Block()
            self.speed_cache.change()

    def init(self):
        super().init()
        self.pre_division_task()
    def main(self):
        return super().main()

class WebResouseTemp(WebResouseBuffer, WebResouseFile):

    def __init__(self, url, buffer_size) -> None:
        super().__init__(url, buffer_size)
        self.file = None
    def init(self):
        super().init()
        self.file = aiofiles.tempfile.TemporaryFile('w+b')
    def close(self):
        return super().close()


    





