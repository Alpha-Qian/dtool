import asyncio, httpx, aiofiles
from asyncio import Event,Lock
import pathlib
import pickle
import time
from models import PosList,monitor

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
        self.filename = url.split('/')[-1]
        self.file = await aiofiles.open(self.filename,'wb')
        self.accept_range = None
        self.file_size = None
        self.downed_size = 0

        self.start_list = PosList()
        self.end_list = PosList()
        self.stop_list = PosList()#存储已分配进度

        self.filelock = Lock()
        self.start = Event()
        self.stop = Event()
        self.dumps = Event()

    async def download(self):
        async with asyncio.TaskGroup() as tg:
            self.task_group = tg
            tg.create_task(self.down_control(tg))
            tg.create_task(self.down_block(save_info= True))
            tg.create_task(self.down_control())
        self.file.close()

    async def down_control(self,task_group):
        await self.start.wait()
        if not self.accept_range:
            return
        while 1:
            if 1==1:
                asyncio.create_task(self.create_task())

    def create_task(self):
        max_empty = 0 
        for i,e,s in range(len(self.end_list)-1),self.end_list[:-1],self.start_list[1:]:
            if max_empty < s-e:
                index = i
                max_empty = s-e
        return int(self.start_list[index+1] - self.end_list[index]/2)

    def save_info(self,headers):#存在问题
        self.headers=headers
        self.file_size = int(headers['content-length'])#####
        self.start_list.add(self.file_size)
        self.accept_range = 'accept-ranges' in headers
        self.start.set()

    async def down_block(self,start_pos = 0,/,save_info = False):
        #start_list = self.start_list
        self.start_list.add(start_pos)
        writen_pos = start_pos
        self.end_list.add(writen_pos)
        self.stop_list.add(stop_pos)######
        headers = {"Range": f"bytes={start_pos}-{self.file_size-1}"}
        async with self.client.stream('GET',self.url,headers = headers) as response:

            if save_info:
                if await self.save_info(response.headers):
                    asyncio.create_task(self.down_control)
            stop_pos = self.file_size#defaut stop_pos

            task_finish = False
            async for chunk in response.aiter_bytes():#<--待修改以避免丢弃多余的内容
                self.downloading.wait()
                len_chunk = len(chunk)

                for i in self.start_list:
                    if start_pos < i < stop_pos:
                        stop_pos = i
                
                if writen_pos + len_chunk > stop_pos:
                    task_finish = True
                    chunk = chunk[: stop_pos - writen_pos]
                    len_chunk = len(chunk)
                                
                async with self.filelock:
                    await self.file.seek(writen_pos)
                    await self.file.write(chunk)
                
                writen_pos += len_chunk
                self.end_list.move(writen_pos,len_chunk)
                self.downed_size += len_chunk
                
                if task_finish:
                    self.end_list.remove(writen_pos)
                    self.start_list.remove(stop_pos)
                    break
                elif stop_pos - writen_pos < len_chunk:
                    pass


    def incorp_list(self):
        for i in range(len(self.end_list)):
            if self.end_list[i] == self.start_list[i+1]:
                del self.end_list[i],self.start_list[i+1]
    
    async def get_info(self):
        async with client.stream('HEAD',self.url) as response:
            self.save_info(response)
    
    async def stop(self):
        for i in self.task_group._task:
            i.cancel()
    
    async def dumps(self):
        await self.stop()
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
    async def stop(self):
        self.task.cancel()




async def main():
    #url = 'https://' + input('https://')
    url='https://f-droid.org/repo/com.termux_1000.apk'
    await asyncio.create_task(DownFile(url).download())
if __name__ =='__main__':
    asyncio.run(main())
    print('end')
