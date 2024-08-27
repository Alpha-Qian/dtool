import asyncio,httpx,aiofiles
from asyncio import Task
import dtool
import time

class Block:
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
        

class BlockList:
    '''list[ Chunk(start, process, plan_state:bool),* ]'''
    __slots__ = ('_list','file_size')

    def __init__(self,file_size) -> None:
        self.file_size = file_size
        self._list :list[Block]= []

    def __len__(self):
        return len(self._list)
    
    def __iter__(self):
        return iter(self._list)
    
    def __getitem__(self,key) -> Block:
        return self._list[key] if key < len(self) else Block(self.file_size, None, None)
    
    def start_index(self, start_pos:int) -> int:
        for i in range(len(self)):
            if self[i].start == start_pos:
                return i
        raise KeyError('cannot find the start_pos')

    def end_index(self, end_pos:int) -> int:
        for i in range(len(self)):
            if self[i].end == end_pos:
                return i
        raise KeyError('cannot find the end_pos')


    def add (self,start_pos:int):
        '''add a new task'''
        for i in range(len(self)):
            if start_pos < self[i].start:
                self._list.insert( Block(start_pos, start_pos, True) )
                return
        self._list.append( Block(start_pos, start_pos, True) )
    
    def record(self, stat_pos, mov_len):
        self[self.start_index(stat_pos)].end += mov_len
        
    def remove(self,start_pos):
        '''called when task remove'''
        self._list[self.start_index(start_pos)].state = False

    
    def empty_chunk(self) -> list[Block]:
        chunks = []
        for i in range(len(self)):
            chunks.append( Block( self[i].end, self[i+1].start, self[i].state ))
    
    def unfinish_chunk(self) -> list[Block]:
        chunks = []
        for i in range(len(self)):
            if self[i].state == True:
                chunks.append( Block( self[i].end, self[i+1].start,True ) )#   允许self[i+1]原因见__getitem__
        return chunks
    
    def unplan_chunk(self) -> list[Block]:
        chunks = []
        for i in range(len(self)):
            if self[i].state == False:
                chunks.append( Block( self[i].end, self[i+1].start, False ) )
        return chunks

    def len_working_chunk(self) -> int:
        length = 0
        for i in self:
            if i.state == True:
                length += 1
        return length

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


class SpeedMonitor:
    def __init__(self,mission:dtool.DownloadFile) -> None:
        self.mission = mission
        self.process = mission.process
        self.time = time.time()
    
    def __next__(self):
        old_process = self.process
        old_time = self.time
        self.process = self.mission.process
        self.time = time.time()
        return (self.process - old_process) / (self.time - old_time) 
    
    def reset(self,):
        self.process = self.mission.process
        self.time = time.time()

    def get(self):
        time.sleep(1)
        return (self.mission.process - self.process) / (time.time() - self.time)
    
    async def aget(self,second:int = 1):
        process = self.mission.process
        t = time.time()
        await asyncio.sleep(second)
        return (self.mission.process - process)/(time.time()-t)

class SpeedCacher:
    def __init__(self,mission,block_num=0) -> None:
        self.speed = 0
        self.old_speed = 0
        self.change_num:int = block_num
        self.mission:dtool.DownloadFile = mission
        self.monitor = SpeedMonitor(mission)
        self.max_speed_per_thread = 0
    def reset(self,block_num):
        self.speed = 0
        self.old_speed = 0
        self.max_speed_per_thread = 0
        self.change_num = block_num

    def change(self,change_num:int = 1):
        if change_num != 0:
            self.old_speed = self.speed
            self.change_num = change_num

    def get(self):
        self.speed = next(self.monitor)
        if (i := self.speed/self.mission.task_num) > self.max_speed_per_thread:
            self.max_speed_per_thread = i
        return (self.speed - self.old_speed) / self.change_num /self.max_speed_per_thread




class SpeedStatis:
    def __init__(self,mission:dtool.DownloadFile) -> None:
        self.list :list[int]=[]
        self.monitor = SpeedMonitor(mission)
        self.num = 1
    def reset(self):
        self.list :list[int] = []
        self.monitor.reset()
        self.num = 1
    def change(self,num:int):
        speed = next(self.monitor)
        if num > len(self.list):
            self.list += [0] * (num - len(self.list))
        self.list[self.num] = speed
    def check(self) -> bool:
        if self.list[self.num]/self.num *0.1 > self.list[self.num] - self.list[self.num - 1]:
            return True
        else:
            return False


class TaskCoordinator:
    def __init__(self) -> None:
        self._enter = asyncio.Lock()
        self._exit = asyncio.Lock()
        self._enter._locked = True #在unlock中释放，在enter中获取
        self._exit._locked = True #在exit中释放,在unlock中获取

    async def __aenter__(self):
        await self._enter.acquire()

    async def __aexit__(self,exc,excv,track):
        self._exit.release()

    async def unlock(self):
        self._enter.release()
        await self._exit.acquire()

    def enter(self):
        return self.__aenter__()
    def exit(self,exc=None,excv=None,track=None):
        return self.__aexit__(exc,excv,track)
        

class EmptyBlock:
    __slot__=('process', 'end')
    def __init__(self, process, end) -> None:
        self.process = process
        self.end = end
    def __repr__(self) -> str:
        return f'EmptyBlock({self.process},{self.end})'
    def __eq__(self, value) -> bool:
        return self.process == value.process and self.end == value.end 
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

class MatePoint(type):
    def __getattribute__(cls, name: str):
        def method(self,*arg):
            super().__getattribute__(name)()
        return super().__getattribute__(name)