import aiofiles
from loguru import logger
import aiofiles.base
import asyncio, httpx, aiofiles
from asyncio import Event,Lock
import dtool.models as models
httpx.Client

class DownloadControl:
    def __init__(self, url,pre_task_num = 1, auto= True) -> None:
        self.mission= DownloadFile(url)
        self.i = 0.1
        self.task = asyncio.create_task(self.mission.main(pre_task_num,auto))
        self.speed_monitor = models.SpeedMonitor(self.mission)
        self.connect_control = models.SpeedCacher(self.mission)
    def check(self):
        if self.connect_control.get()>= self.i:
            self.mission.re_division_task()
            self.connect_control.change()
    
    @property
    def speed(self):
        return next(self.speed_monitor)
    @property
    def file_size(self):
        return self.mission.file_size
    @property
    def process(self):
        return self.process
    @property
    def task_num(self):
        return self.mission.task_num
    @property
    def time_left(self):
        if self.speed == 0:
            return 1145141919810
        return (self.file_size - self.process)/self.speed

class Mission:
    def __init__(self) -> None:
        self.pending_tasks = []
        self.loop = asyncio.get_event_loop()
    def run(self):
        self.loop.run_in_executor()
    async def main(self):
        async with asyncio.TaskGroup as tg:
            asyncio.sleep(0)
    def new_task_threadsafe(self, url):
        self.loop.call_soon_threadsafe(self.new_task(url))
    def new_task(self, url):
        self.loop.create_task(DownloadFile(url).main())



class DownloadFile:
    client = httpx.AsyncClient()

    def __init__(self, url, path, file = None):
        self.url = url
        self.path = path
        self.filename = url.split('/')[-1]
        self.task_num = 0
        
        
        self.saved_info:bool = False
        self.headers = None
        self.download_prepare = models.TaskCoordinator()
        self.accept_range:bool = None
        self.file_size = 1

        self.file_lock = Lock()
        self.process = 0
        self.task_list:list[DownBlocks] = []
        #self.task_group = asyncio.TaskGroup()
        
        self.speed_cache = models.SpeedCacher(self)
        


    def pre_division_task(self,  block_num):
        block_size = self.file_size // block_num
        if block_num != 0:
            for i in range(block_size, self.file_size - block_num, block_size):
                self.cut_block(i)()
        self.speed_cache.reset(block_num)
        #return range(block_num, block_size, self.file_size)
    
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


    def cut_block(self, start_pos:int):
        '''自动根据开始位置创建新任务,底层API'''
        if len(self.task_list) > 0 and start_pos < self.task_list[-1].end:
            for block in self.task_list:
                if block.process < start_pos < block.end:
                    new_block = DownBlocks(start_pos, block.end, self) #分割
                    block.end = start_pos
                    self.task_list.insert(self.task_list.index(block)+1,new_block)
                    #asyncio.create_task(new_block.run())
                    return new_block
            raise
        new_block = DownBlocks(start_pos, self.file_size, self)
        self.task_list.append(new_block)
        #asyncio.create_task(new_block.run())
        return new_block

        
    async def main(self, pre_task_num = 1, auto = True, max_task_num = 256):
        self.cut_block(0)()
        async with self.download_prepare:
            self.saved_info = True
            for i in self.headers:
                print(i,self.headers[i])
            if 'content-length' in self.headers:
                self.file_size = int(self.headers['content-length'])
                self.accept_range = 'accept-ranges' in self.headers
            else:
                self.file_size = 1
                self.accept_range = False
            self.task_list[-1].end = self.file_size
            #print(self.task_list[-1].end)
            self.file = await aiofiles.open(self.filename,'w+b')
            self.pre_division_task(pre_task_num)
        while self.process != self.file_size:
            await asyncio.sleep(1)
            
            if auto and self.task_list and (i:=self.speed_cache.get()) >= 0.1 :
                self.re_division_task()
            print(f'get\t{i}\ttask_num\t{self.task_num}')
            print(f'process\t{self.process/self.file_size}\tleft\t{self.file_size - self.process}')
            '''   
            if self.speed_cache.check():
                print('new task')
                self.re_division_task()'''
                
    def __iter__(self):
        start = 0
        data_block = []
        for i in self.task_list:
            data_block.append((start,i.process))
            start = i.end
        return data_block
    def stop(self):
        for i in self.task_list:
            i.task.cancel()


    


class DownBlocks():
    client = httpx.AsyncClient()

    def __init__(self, start, end, mission:DownloadFile):
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
            
            async for chunk in response.aiter_raw(16834):
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
    
    async def cancel(self):
        self.task.cancel()



class Stream(DownloadFile):
    def __init__(self, url, buffing = 16777216 ,step = 16384):#16MB
        self.url = url
        self.task_num = 0
        
        self.saved_info:bool = False
        self.download_prepare = models.TaskCoordinator()
        self.headers = None
        self.accept_range:bool = None
        self.file_size = 1

        self.process = 0
        self.buffing = buffing
        self.step = step

        self.task_list:list[DownBlocks] = []
        #self.task_group = asyncio.TaskGroup()
        
        self.speed_cache = models.SpeedCacher(self)
    def cut_block(self, start_pos: int):
        return super().cut_block(start_pos)
    


class DownBlocks():
    client = httpx.AsyncClient()

    def __init__(self, start, end, mission:DownloadFile):
        self.process = start
        self.end = end
        self.mission = mission
        self.running = False
        self.buffer = bytearray()

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
                await mission.download_prepare.unlock(response)
            
            async for chunk in response.aiter_raw(16834):   #<--待修改以避免丢弃多余的内容
                len_chunk = 16834
                if self.process + len_chunk < self.end:
                    self.buffer += chunk
                    self.process += len_chunk
                    mission.process += len_chunk
                else:
                    self.buffer += chunk[:self.end - self.process]
                    self.process = self.end
                    mission.process += self.end - self.process

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
    
    async def cancel(self):
        self.task.cancel()




async def main():
    #url = 'https://' + input('https://')
    url='https://f-droid.org/repo/com.termux_1000.apk'
    url = 'https://dldir1.qq.com/qqfile/qq/QQNT/Windows/QQ_9.9.15_240822_x64_01.exe'
    url = 'https://github.com/XiaoYouChR/Ghost-Downloader-3/blob/main/app/common/download_task.py'
    await asyncio.create_task(DownloadFile(url,path='./').main(pre_task_num=int(input('->')),auto= True))
if __name__ =='__main__':
    asyncio.run(main())
    print('end')
