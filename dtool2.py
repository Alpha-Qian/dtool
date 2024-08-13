import asyncio,httpx,aiofiles
from asyncio import create_task,Event
client = httpx.AsyncClient()
class DownFile:
    def __init__(self,url,file,) -> None:
        self.url = url
        self.file_name = 'unkown'
        self.file_size = None
    async def run(self):
        self.file = await aiofiles.open(self.file_name)
        self.workers = []
        self.connected = Event()
        self.workers.append(self.new_task(0,0,0,True,event= self.connected))
        self.connected.wait()
        self.save_info(self.workers[0].head)
        if self.accept_range:
            max_remaid = 0
            for i in self.workers:
                remaid = i.end - i.process
                if max_remaid < remaid:
                    max_remaid = remaid
                    max_remaid_task = i
            
                

    def save_info(self,head):
        self.file_size = int(head['content-length'])#####
        self.accept_range = 'accept-ranges' in head


    async def new_task(self,start,end,save_head = False,event = None):
        worker = DownBlock(self.url,start,end,self.file_size,save_head)
        create_task(worker.run())
        return worker

        
class DownBlock:
    
    def __init__(self,url,start,end,file,file_size,save_head) -> None:
        self.url = url
        self.start = start
        self.process = start
        self.end = end
        self.file = file
        self.lock = asyncio.Lock()
        self.file_size = file_size
        self.save_head = save_head
    async def run(self,event = None):
        self.working = True
        try:
            headers = {"Range": f"bytes={self.start}-{self.file_size - 1}"} if self.save_head == False else {}
            async with client.stream('GET',self.url,headers=headers) as response:
                if self.save_head == True:
                    self.head = response.headers
                    event.set()
                chunklen = 16384
                async for i in response.aiter_raw(chunklen):
                    length = len(i)
                    async with self.lock():
                        if self.process + len(i) > self.end:
                            await self.file.seek(self.end)
                            if i[-8:] != await self.file.read(8):
                                raise Exception()
                        await self.file.seek(self.process)
                        await self.file.write(i)
                    self.process += length
                    if self.process + chunklen >= self.end:
                        chunklen = self.end - self.process + 8


        except:
            pass
        finally:
            self.working = False





