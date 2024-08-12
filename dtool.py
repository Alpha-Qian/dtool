import aiofiles
import asyncio, httpx, aiofiles
from asyncio import Event,Lock
import pathlib
import pickle
import time
from models import PosList,ChunkList,monitor,Chunk,TaskList

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

        self.file_cro = aiofiles.open(self.filename,'w+b')# w+b:覆盖读写，会清除数据 r+b:插入读写
        self.accept_range = None
        self.file_size = None
        self.downed_size = 0
        self.speed = 0
        self.task_num = 0

        self.chunk_list = ChunkList()
        self.task_group :list[asyncio.Task]= []

        self.filelock = Lock()
        self.get_head =Event()
        self.start = Event()
        self.stop = Event()
        self.dumps = Event()

    async def download(self,targt_task_num,auto = True):
        self.file = await self.file_cro
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.down_block(save_info = True))
            await self.get_head.wait()
            if self.accept_range == True:
                while self.downed_size < self.file_size:
                    if self.task_num < targt_task_num:
                        tg.create_task(self.down_block( self.load_balance() ))
                    

        self.file.close()

        

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
        self.accept_range = 'accept-ranges' in headers
        self.get_head.set()

    async def down_block(self,start_pos = 0,/,save_info = False):
        self.task_num += 1
        try:
            self.task_group.append(asyncio.current_task())
            chunk_list = self.chunk_list
            chunk_list.add(start_pos)
            process = start_pos
            headers = {"Range": f"bytes={start_pos}-{self.file_size-1}"}
            async with self.client.stream('GET',self.url,headers = headers) as response:
                if save_info:
                    self.save_info(headers)

                stop_pos = self.file_size#defaut stop_pos
                task_finish = False
                t0 = time.time()

                len_stream = 16384
                async for chunk in response.aiter_bytes(len_stream):   #<--待修改以避免丢弃多余的内容
                    len_chunk = len(chunk)
                    for i in chunk_list:
                        if start_pos < i.start < stop_pos:
                            stop_pos = i.start
                    if process + len_chunk > stop_pos:
                        chunk = chunk[: stop_pos - process]
                        len_chunk = len(chunk)
                    
                    async with self.filelock:
                        await self.file.seek(process)
                        await self.file.write(chunk)
                    process += len_chunk
                    chunk_list.record(process,len_chunk)
                    self.downed_size += len_chunk
                    
                    if stop_pos - process < len_stream:
                        len_stream = stop_pos - process + 8 # 8是冗余校验
        except Exception as exc:
            print(exc.args)
        else:
            pass
        finally:
            self.task_num -= 1
            chunk_list.remove(start_pos)
    
    async def get_info(self):
        async with self.client.stream('HEAD',self.url) as response:
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
    def __init__(self,url,file,start,end):
        self.url = url
        self.file = file
        self.start = start
        self.end = end
        self.process = start
    async def run(self):
        self.task_num += 1
        try:
            self.task_group.append(asyncio.current_task())
            chunk_list = self.chunk_list
            chunk_list.add(start_pos)
            process = start_pos
            headers = {"Range": f"bytes={start_pos}-{self.file_size-1}"}
            async with self.client.stream('GET',self.url,headers = headers) as response:
                if save_info:
                    self.save_info(headers)

                stop_pos = self.file_size#defaut stop_pos
                task_finish = False
                t0 = time.time()

                len_stream = 16384
                async for chunk in response.aiter_bytes(len_stream):   #<--待修改以避免丢弃多余的内容
                    len_chunk = len(chunk)
                    for i in chunk_list:
                        if start_pos < i.start < stop_pos:
                            stop_pos = i.start
                    if process + len_chunk > stop_pos:
                        chunk = chunk[: stop_pos - process]
                        len_chunk = len(chunk)
                    
                    async with self.filelock:
                        await self.file.seek(process)
                        await self.file.write(chunk)
                    process += len_chunk
                    chunk_list.record(process,len_chunk)
                    self.downed_size += len_chunk
                    
                    if stop_pos - process < len_stream:
                        len_stream = stop_pos - process + 8 # 8是冗余校验
        except Exception as exc:
            print(exc.args)
        else:
            pass
        finally:
            self.task_num -= 1
            chunk_list.remove(start_pos)

    async def  verify(self):#合并验证
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
