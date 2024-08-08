import asyncio, httpx, aiofiles
import pathlib
import pickle
import time
from database import PosList

client = httpx.AsyncClient()
tasks = []
result = []
Path =''
def new(url,path=None):
    asyncio.run(anew(url,Path))
def new_urls(urls,path=None):
    asyncio.run(anew_urls(urls))
async def anew(url,path=None):
    new_task = DownFile(url)
    await new_task.down_init()
async def anew_urls(urls,path=None):
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            tasks.append(tg.creat_task(url))


asyncio.Semaphore
asyncio.TaskGroup

class DownControler:
    def __init__(self,url,max_sem=32) -> None:
        self.url=url
        self.max_sem = max_sem
        self.down_file = DownFile(url)
    
    def __getattr__(self, name):
        return getattr(self.down_file, name)
    
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
        return zip(self.end_list[:-1],self.start_list[1:])
    
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

    def __init__(self, url, ):
        self.url = url
        self.filename = url.split('/')[-1]
        self.accept_range = None
        self.file_size = None
        self.downed_size = 0
        self.start_list = PosList([])
        self.end_list = PosList([])
        self.filelock = None

    async def get_headers(self):
        self.file = aiofiles.open(self.filename,mode='wb')
        response = await self.client.head(self.url)
        self.headers=response.headers
        self.file_size = int(self.headers['content-length'])
        self.start_list.add(self.file_size)
        self.accept_range = 'accept-ranges' in self.headers
            
    async def download_main(self):
        self.downed_size = 0
        self.filelock = asyncio.Lock()
        self.sem = asyncio.Semaphore(0)#信号量
        self.file =await self.file.__aenter__()
        self.sem_num =32
        async with asyncio.TaskGroup() as tg:
            self.task_group = tg
            #tg.create_task(self.download_control(tg))
            tg.create_task(self.down_block(0))
            tg.create_task(self.down_block(52428800))
        await self.file.close()
        
    async def task_creater(self,):
        pass
    async def get_speed():
        s0,s1,s2,s3,s4 = 0,0,0,0,0
        while 1:
            break
            s1,s2,s3,s4 = s0,s1,s2,s3

    async def down_block(self,start_pos,res =None):
        
        self.start_list.add(start_pos)

        writen_pos = start_pos
        self.end_list.add(writen_pos)
        headers = {"Range": f"bytes={start_pos}-{self.file_size-1}"}

        async with self.client.stream('GET',self.url,headers = headers) as response:
            end_pos = self.file_size
            self.sem.acquire()#获取信号
            async for chunk in response.aiter_bytes():#<--待修改以避免丢弃多余的内容
                self.sem.release()#释放信号
                len_chunk = len(chunk)
                for i in self.start_list:
                    if start_pos < i < end_pos:
                        end_pos = i

                if writen_pos + len_chunk <= end_pos:
                    async with self.filelock:
                        await self.file.seek(writen_pos)
                        await self.file.write(chunk)
                    self.downed_size += len_chunk
                    self.end_list.move(writen_pos,len_chunk)
                    writen_pos += len_chunk
                    self.sem.acquire()#进入下一个循环前获取信号

                else:
                    async with self.filelock:
                        await self.file.seek(writen_pos)#
                        await self.file.write(chunk[ : end_pos-writen_pos])
                    self.downed_size += end_pos - writen_pos
                    self.end_list.move(writen_pos,end_pos)
                    break
    async def restart(self):
        pass 
    async def stop(self,):
        while self.sem_num > 0:

    async def dumps(self,):
        return pickle.dumps(self)
    @classmethod
    async def loads(cls,data):
        obj = pickle.loads(data)
        if type(obj) != cls:
            raise Exception
        return obj



async def main():
    #url = 'https://' + input('https://')
    url='https://f-droid.org/repo/com.termux_1000.apk'
    await asyncio.create_task(DownFile(url).download())
if __name__ =='__main__':
    asyncio.run(main())
    print('end')
