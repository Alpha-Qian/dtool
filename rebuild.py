import asyncio, httpx, aiofiles
import models





class WebResouse:
    '''基类，只关心资源和连接状况'''
    client = httpx.AsyncClient

    def __init__(self, url) -> None:
        self.url = url
        self.task_list:list[ConnectBase] = []
        self.task_num = 0

        self.inited = False
        self.init_prepare = models.TaskCoordinator()
        self.headers = None
        self.res_size = 0
        self.accept_range = None

    def new_block(self, start, end):
        return ConnectBase(start, end, self)

    def cut_block(self, start_pos:int, end_pos:int|None = None):
        '''自动根据开始位置创建新任务,底层API'''
        if len(self.task_list) > 0 and start_pos < self.task_list[-1].end:
            for block in self.task_list:
                if block.process < start_pos < block.end:
                    new_block = ConnectBase(start_pos, block.end, self) #分割
                    block.end = start_pos
                    self.task_list.insert(self.task_list.index(block)+1,new_block)
                    #asyncio.create_task(new_block.run())
                    return new_block
            raise Exception('重复下载')
            if end_pos is not None:
                new_block = ConnectBase(start_pos, end_pos, self)
                self.task_list
        new_block = ConnectBase(start_pos, self.res_size, self)
        self.task_list.append(new_block)
        #asyncio.create_task(new_block.run())
        return new_block
    
    def init(self):
        self.saved_info = True
        if 'content-length' in self.headers:
            self.file_size = int(self.headers['content-length'])
            self.accept_range = 'accept-ranges' in self.headers
        else:
            self.file_size = 1
            self.accept_range = False
        self.task_list[-1].end = self.file_size
    
    async def main(self):
        self.cut_block(0)()
        async with self.init_prepare:
            self.init()

    def call_back(self,task):
        pass
    def close(self):
        pass


class WebResouseBuffer(WebResouse):

    def __init__(self, url, buffer_size) -> None:
        super().__init__(url)
        self.process = 0
        self.buffering = buffer_size

    def pre_division_task(self):
        pass

    async def __anext__(self):
        for i in self.task_list:
            if i.start <= self.process < i.process:
                pass


class WebResouseStream(WebResouseBuffer):

    async def __anext__(self):
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        await fut
        #raise StopAsyncIteration
        return super().__anext__()
    def __next__(self):
        if self.loop is None:
            self.loop = asyncio.get_event_loop()
        return self.loop.run_until_complete( anext(self) )

class WebResouseAll(WebResouse):
    '''需要确保所有部分下载完成'''

    def __init__(self, url) -> None:
        super().__init__(url)
        self.process = 0

    def init(self, pre_task_num):
        super().init()
        self.pre_division_task(pre_task_num)
    
    def pre_division_task(self,  block_num):
        block_size = self.file_size // block_num
        if block_num != 0:
            for i in range(block_size, self.file_size - block_num, block_size):
                self.cut_block(i)()
        self.speed_cache.reset(block_num)
    
 
    
    def main(self, pre_task_num):
        return super().main()

class WebResouseFile(WebResouse):
    '''需要初始化文件'''

    def __init__(self, url) -> None:
        super().__init__(url)
        self.speed_cache = models.SpeedCacher(self)
    
    def init(self):
        super().init()
        self.file = aiofiles.open('','w+b')
    
    
class WebResouseDownload(WebResouseFile, WebResouseAll):
    
    def re_division_task(self):
        '''负载均衡，创建任务并运行'''
        max_remain = 0
        cut_block = True
        for i in self.task_list:
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


    




class ConnectBase:
    '无缓存基类'
    client = httpx.AsyncClient()
    
    def __init__(self, start, end, mission:WebResouse):
        self.start = start
        self.process = start
        self.end = end
        self.mission = mission
        self.running = False

    async def run(self):
        self.running = True
        mission = self.mission
        task_list = mission.task_list

        if mission.saved_info:
            headers = {"Range": f"bytes={self.process}-{mission.file_size-1}"}
        else:
            headers = dict()
        async with self.client.stream('GET',mission.url,headers = headers) as response:
            if not mission.saved_info:
                mission.headers = response.headers
                await mission.download_prepare.unlock()
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
            self.mission.task_list.remove(self)
            self.mission.re_division_task()
        finally:
            self.running = False
            print(f'callback\t{self.mission.task_num - 1}')
            self.mission.task_num -= 1
            self.mission.call_back()


class ConnectBuffer(ConnectBase):
    '''有缓存类'''

    def __init__(self, start, end, web_resouse: WebResouse) -> None:
        super().__init__(start, end, web_resouse)
        self.start = start
        self.buffer = bytearray()

    async def main(self, response: httpx.Response):
        async for chunk in response.aiter_raw(16384):
            len_chunk = 16834
            if self.process + len_chunk < self.end:
                self.buffer += chunk
                self.process += len_chunk
            else:
                self.buffer += chunk[: self.end - self.process]
                break
    
    async def pop(self,size = -1):
        if size == -1:
            i = self.buffer
            self.buffer = bytearray()
            return i
        else:
            i = self.buffer[:size]
            del self.buffer[:size]
            return i


class ConnectFile(ConnectBase):
    '''异步写入文件，关心整个文件的处理情况'''
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

                        if (i := mission.task_list.index(self) + 1) == len(mission.task_list):
                            await mission.file.truncate()
                        elif self.process + len_chunk < mission.task_list[i].process :
                            i = await mission.file.read(self.process + len_chunk - self.end)#
                            if i == check_chunk:
                                print('校验成功')
                                break
                            else:
                                self.end = mission.task_list[i].process
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

