import asyncio,httpx,aiofiles
from asyncio import Task
import dtool

class Chunk:
    __slots__ = ('start','end','state')
    def __init__(self, start_pos:int, end_pos:int, state:bool = False) -> None:
        self.start = start_pos
        self.end = end_pos
        self.state = state
    
    def __len__(self):
        return self.end - self.start
    
    def __getitem__(self,key) -> int|bool:
        match key:
            case 0:
                return self.start
            case 1:
                return self.end
            case 2:
                return self.state
        raise KeyError()
        

class ChunkList:
    '''list[ Chunk(start, process, plan_state:bool),* ]'''
    __slots__ = ('_list','file_size')

    def __init__(self,file_size) -> None:
        self.file_size = file_size
        self._list :list[ Chunk ]= []

    def __len__(self):
        return len(self._list)
    
    def __iter__(self):
        return iter(self._list)
    
    def __getitem__(self,key) -> Chunk:
        return self._list[key] if key < len(self) else Chunk(self.file_size, None, None)
    
    def start_index(self, start_pos:int) -> int['index']:
        for i in range(len(self)):
            if self[i].start == start_pos:
                return i
        raise KeyError('cannot find the start_pos')

    def end_index(self, end_pos:int) -> int['index']:
        for i in range(len(self)):
            if self[i].end == end_pos:
                return i
        raise KeyError('cannot find the end_pos')

    def add (self,start_pos:int):
        '''add a new task'''
        for i in range(len(self)):
            if start_pos < self[i].start:
                self._list.insert( Chunk(start_pos, start_pos, True) )
                return
        self._list.append( Chunk(start_pos, start_pos, True) )
    
    def record(self, stat_pos, mov_len):
        self[self.start_index(stat_pos)].end += mov_len
        
    def remove(self,start_pos):
        '''called when task remove'''
        self._list[self.start_index(start_pos)].state = False

    
    def empty_chunk(self) -> list[Chunk]:
        chunks = []
        for i in range(len(self)):
            chunks.append( Chunk( self[i].end, self[i+1].start, self[i].state ))
    
    def unfinish_chunk(self) -> list[Chunk]:
        chunks = []
        for i in range(len(self)):
            if self[i].state == True:
                chunks.append( Chunk( self[i].end, self[i+1].start,True ) )#   允许self[i+1]原因见__getitem__
        return chunks
    
    def unplan_chunk(self) -> list[Chunk]:
        chunks = []
        for i in range(len(self)):
            if self[i].state == False:
                chunks.append( Chunk( self[i].end, self[i+1].start, False ) )
        return chunks


class TaskList:
    __slots__ = ('_list',)

    def __init__(self) -> None:
        self._list:list[Task] = []
    
    def __len__(self):
        self.check()
        return len(self._list)
    
    async def __await__(self):
        for i in self._list:
            await i

    async def __aenter__(self):
        return self
    
    async def __aexit__(self,exc_type, exc_value, traceback):
        await self
        return False
    
    def check(self):
        for i in range(len(self._list)):
            if self._list[i].done() == True:
                del self._list[i]

    def new(self,coro):
        task = asyncio.create_task(coro)
        self._list.append(task)
    
    def add(self,task:Task):
        self._list.append(task)

    
        


class FileInfo:
    pass




class PosList:          #已弃用
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
