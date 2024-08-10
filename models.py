import asyncio,httpx,aiofiles
import dtool

class PosList:
    '''即将弃用'''
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
    '''list[ (start, process, plan_state:bool),* ]'''
    def __init__(self,file_size) -> None:
        self.file_size = file_size
        mark = (file_size,None,None)
        self._list :list[ tuple[int, int, bool] ]= []

    def __len__(self):
        return len(self._list)
    
    def __iter__(self):
        return iter(self._list)
    
    def __getitem__(self,key) -> tuple[int,int,bool]:#???????
        return self._list[key] if key < len(self) else (self.file_size,)
    
    def find_index(self,start_pos:int) -> int['index']:
        for i in range(len(self)):
            if self._list[i][0] == start_pos:
                return i
        raise KeyError('cannot find the start_pos')
    
    def add (self,start_pos):
        '''add a new task'''
        for i in range(len(self)):
            if start_pos < self[i][0]:
                self._list.insert((start_pos,start_pos,True))
                return
        self._list.append((start_pos,start_pos,True))
    
    def record(self,stat_pos,end_pos):
        self[self.find_index(stat_pos)][1]=end_pos
        
    def remove(self,start_pos):
        '''called when task remove'''
        self._list[self.find_index(start_pos)][2] = False

    def finish_chunk(self):
        chunks = []
        for i in self:
            chunks.append( i[0, 2] )
        
    def unfinish_chunk(self):
        chunks = []
        for i in range(len(self)):
            if self[i][2] == True:
                chunks.append( (self[i][1], self[i+1][0]) )
          
    def unplan_chunk(self):
        chunks = []
        for i in range(len(self)):
            if self[i][2] == False:
                chunks.append( (self[i][1], self[i+1][0]) )
    


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
