import asyncio
import aiofiles
import httpx
import pathlib
import pickle
import time

client = httpx.AsyncClient()
tasks = []
result = []
Path =''
def new(url,path=None):
    asyncio.run(anew(url,Path))

def new_urls(urls,path=None):
    asyncio.run(anew_urls(urls))

async def anew(url,path=None):
    new_task = DownloadFile(url)
    await new_task.down_init()
async def anew_urls(urls,path=None):
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            tasks.append(tg.creat_task(url))

class DownloadFile:    
    client = httpx.AsyncClient()

    def __init__(self, url, ):
        self.url = url
        self.filename = url.split('/')[-1]
        self.accept_range = None
        self.file_size = None
        self.start_list = PosList([])
        self.end_list =PosList([])
    async def download(self):
        respose = await asyncio.create_task(self.get_headers())
        if self.accept_range:
            await asyncio.create_task(self.download_main(respose))
        else:
            pass

    async def get_headers(self):
        self.file = aiofiles.open(self.filename,mode='wb')
        response = await self.client.head(self.url)
        self.headers=response.headers
        self.file_size = int(self.headers['content-length'])
        self.start_list.add(self.file_size)
        self.accept_range = 'accept-ranges' in self.headers
            
    async def download_main(self,res=None):
        self.down_to = 0
        self.reslock = asyncio.Lock()
        self.file =await self.file.__aenter__()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.down_block(0,res))
            tg.create_task(self.down_block(52428800))
            newtime=time.time() 
            a='''
            while 1:
                old_to = self.down_to
                oldtime=newtime
                await asyncio.sleep(0.05)
                newtime=time.time()
                speed = self.down_to - old_to
                print(f'{self.down_to-self.file_size},{speed/(1024*1024)/(newtime-oldtime):.5}Mb/s----------' , end = '\r')
                if self.down_to ==self.file_size:
                    break'''
        await self.file.close()
                


    async def down_block(self,start_pos,res =None):
        
        self.start_list.add(start_pos)

        writen_pos = start_pos
        self.end_list.add(writen_pos)
        headers = {"Range": f"bytes={start_pos}-{self.file_size-1}"}

        async with self.client.stream('GET',self.url,headers = headers) as response:
            end_pos = self.file_size

            async for chunk in response.aiter_bytes():#<--待修改以避免丢弃多余的内容
                len_chunk = len(chunk)
                for i in self.start_list:
                    if start_pos < i < end_pos:
                        end_pos = i

                if writen_pos + len_chunk <= end_pos:
                    async with self.reslock:
                        await self.file.seek(writen_pos)#
                        await self.file.write(chunk)
                    self.down_to += len_chunk
                    self.end_list.move(writen_pos,len_chunk)
                    writen_pos += len_chunk

                else:
                    async with self.reslock:
                        await self.file.seek(writen_pos)#
                        await self.file.write(chunk[ : end_pos-writen_pos])
                    self.down_to += end_pos - writen_pos
                    self.end_list.move(writen_pos,end_pos)
                    break
    async def restart(self):
        pass
    async def stop(self,):
        pass
    async def dumps(self,):
        return pickle.dumps(self)
    @classmethod
    async def loads(cls,data):
        obj = pickle.loads(data)
        if type(obj) != cls:
            raise Exception
        return obj
    async def get_data_block(self,):
        pass

class PosList:
    '''待修改'''
    def __init__(self,/,*arg,**kwarg):
        self._list=list(*arg,**kwarg)
        self.sort()
    def sort(self,**kwarg):
        self._list.sort(**kwarg)
    def __getitem__(self,key):
        return self._list[key]
    def __len__(self):
        return len(self._list)
    def __iter__(self):
        return iter(self._list)

    def remove(self,value):
        self._list.remove(value)
    def add (self,value):
        for i in range(len(self)):
            if value < self[i]:
                self._list.insert( i, value)
                return
        self._list.append(value)
    def move(self,value,mov):
        self._list[self._list.index(value)] = value + mov

async def main():
    #url = 'https://' + input('https://')
    url='https://f-droid.org/repo/com.termux_1000.apk'
    await asyncio.create_task(DownloadFile(url).download())
if __name__ =='__main__':
    asyncio.run(main())
    print('end')
