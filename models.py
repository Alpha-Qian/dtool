import asyncio,httpx,aiofiles
import dtool

class PosList:
    def __init__(self,/,*arg,**kwarg):
        self._list = []
        #self._list=list(*arg,**kwarg)
        #self.sort()
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


class ChunkList:
    '''[(start,process,end),*]'''
    def __init__(self) -> None:
        self.chunk_list=[]
    def __getitem__(self,key):
        return self.chunk_list[key]
    def __len__(self):
        return len(self.chunk_list)
    def __iter__(self):
        return iter(self.chunk_list)
    
    def new_task(self,start_pos):
        self.chunk_list.append((start_pos,start_pos,en))


class DownBlock:
    def __init__(self,url,start_pos,tracker:PosList):
        self.url=url
        self.start_pos=start_pos
    async def start(self):
        async with httpx.stream('GET',self.url) as response:
            pass

class monitor:
    def __init__(self) -> None:
        self.speed = 0
    async def monitor(self,obj,speed):
        list = []
        obj.downed_size
        asyncio.sleep(1/speed)

        
    async def __aenter__(self,obj):
        self.task = asyncio.create_task(self.monitor(obj))
        return self
        
    async def __aexit__(self):
        await self.task

def repr(bytes):
    pass




class PosInf:
    pass
class NegInf:
    pass
