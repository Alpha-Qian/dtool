import aiofiles
import asyncio, httpx, aiofiles
from asyncio import Event,Lock
import pathlib
import pickle
import time
from models import PosList,ChunkList,monitor

client = httpx.AsyncClient()
tasks = []
result = []
Path =''

asyncio.Semaphore
asyncio.TaskGroup
aiofiles.open()
httpx.AsyncClient().stream
async def test():
    client= httpx.AsyncClient()
    aiofiles.open('')
    async with client.stream('','') as a:
        a
        async for i in a.aiter_bytes():
            pass
    a =await client.stream('','').__aenter__()
    a.aiter_bytes()
    

class DownControler:#改为多文件下载控制
    '''self.max_connect'''
    def __init__(self,max_connect=32) -> None:
        self.max_connect = max_connect
        self.connect_num = 0
        self.speed_list :list[int]= []#统计在不同连接数下的链接速度
    
    async def speed_statistic(self):
        pass

    async def new_url(self,url,path):
        pass

    async def download(self):
        down_file = self.down_file
        controler = asyncio.create_task(self.down_control())
        await asyncio.create_task(down_file.get_headers())
        if down_file.accept_range:
            await asyncio.create_task(down_file.download_main())
        else:
            pass
        #controler.cancel()
        await controler
    
    async def monitor(self):
        len_task = len(self.down_file.task_group)
        len_sem = self.down_file.sem._value
    
    async def down_control(self,contr_func:function[int:'']):
        download_file = self.down_file
        sem = download_file.sem
        self.task_group = download_file.task_group
        while 1:
            sem._value

    async def get_data_chunk(self):
        return zip(self.down_file.start_list,self.end_list)
    async def get_empty_chunk(self):
        return zip(self.down_file.end_list[:-1],self.start_list[1:])

    async def get_speed(self,time):
        size1 = self.down_file.downed_size
        asyncio.sleep(time)
        return (self.down_file.downed_size - size1)/time
    async def speed_monitor(self,time):
        pass
    async def restart(self):
        pass
    async def stop(self):
        pass

class DownFile:
    client = httpx.AsyncClient()

    def __init__(self, url, path):
        self.url = url
        self.path = path
        self.filename = url.split('/')[-1]

        self.file_cro = aiofiles.open(self.filename,'wb')
        self.accept_range = None
        self.file_size = None
        self.downed_size = 0
        self.speed = 0

        self.chunk_list = ChunkList()
        self.task_group :list[asyncio.Task]= []

        self.filelock = Lock()
        self.start = Event()
        self.stop = Event()
        self.dumps = Event()

    async def download(self,targt_task_num,auto = True):
        if len(self.task_group) < targt_task_num:
            self.create_task(self.load_balance())
        if auto:
            pass
        self.file = await self.file_cro
        self.file.close()

    async def down_control(self):
        await self.start.wait()
        speed_list :list[int:'max_speed']= [] 
        if not self.accept_range:
            return
        for i in range(len(self.task_group)):
            asyncio.sleep(0.5)
            if self.task_group[i].done():
                del self.task_group[i]
            if len(speed_list) < len(self.task_group):
                speed_list.append(0)8
            speed_list[ len(self.task_group) ] =
            if self.downed_size < self.file_size:
                asyncio.create_task(self.down_block( self.load_balance()))
                
    def speed_monitor(self):
        times = []
        sizes = []
        while True:
            size = yield
            t=time.time()

            sizes.append()
            times.append(time.time())

            length = len(self.task_group)
            if len(sizes) > length:
                sizes.pop(0)
                times.pop(0)
            yield sum(sizes) / time.time() - times[0]            

            
        

        

    def load_balance(self):        #负载均衡
        chunk_list = self.chunk_list
        max_len = 0
        empty_chunks = chunk_list.empty_chunk()
        for i in empty_chunks:
            length = len(i)
            if i.state == False:
                length *= 2
            if length > max_len:
                max_len = length
                biggest_chunk = i
        if biggest_chunk.state == True:
            return ( biggest_chunk.start + biggest_chunk.end ) // 2
        else:
            return biggest_chunk.start     

    def save_info(self,headers):#存在问题
        self.headers=headers
        self.file_size = int(headers['content-length'])#####
        self.start_list.add(self.file_size)
        self.accept_range = 'accept-ranges' in headers
        self.start.set()

    async def down_block(self,start_pos = 0,/,save_info = False):
        self.task_group.append(asyncio.current_task())

        chunk_list = self.chunk_list
        chunk_list.add(start_pos)

        process = start_pos

        headers = {"Range": f"bytes={start_pos}-{self.file_size-1}"}
        async with self.client.stream('GET',self.url,headers = headers) as response:

            if save_info:
                if await self.save_info(response.headers):
                    asyncio.create_task(self.down_control)
            stop_pos = self.file_size#defaut stop_pos

            task_finish = False
            t0 = time.time()
            async for chunk in response.aiter_bytes():   #<--待修改以避免丢弃多余的内容
                len_chunk = len(chunk)
                t1 = time.time()
                speed = len_chunk / (t1-t0)#在DownChunk中实现
                t0 = t1
                self.downloading.wait()
                

                for i in chunk_list:
                    if start_pos < i[0] < stop_pos:
                        stop_pos = i[0]
                
                if process + len_chunk > stop_pos:
                    task_finish = True
                    chunk = chunk[: stop_pos - process]
                    len_chunk = len(chunk)
                                
                async with self.filelock:
                    await self.file.seek(process)
                    await self.file.write(chunk)
                
                process += len_chunk
                chunk_list.record(process,len_chunk)
                self.downed_size += len_chunk
                
                if task_finish:
                    chunk_list.remove(start_pos)
                    break
                elif stop_pos - process < len_chunk:
                    pass
    
    async def get_info(self):
        async with client.stream('HEAD',self.url) as response:
            self.save_info(response)
    
    async def stop(self):
        for i in self.task_group._task:
            i.cancel()
    
    async def dumps(self):
        await self.stop()
        chunk_list = self.chunk_list
        chunk_list.file_name = self.filename
        return pickle.dumps(self)
   
    @classmethod
    async def loads(cls,data):
        return pickle.loads(data)
    
        obj = pickle.loads(data)
        if type(obj) != cls:
            raise Exception
        return obj



class DownBlocks:
    def __init__(self,task) -> None:
        self.task_list = []
    async def new(self,task):
        self.tasks.append(task)
        pass
    async def speed_monitor(self):
        pass
    async def stop(self):
        self.task.cancel()




async def main():
    #url = 'https://' + input('https://')
    url='https://f-droid.org/repo/com.termux_1000.apk'
    await asyncio.create_task(DownFile(url).download())
if __name__ =='__main__':
    asyncio.run(main())
    print('end')
