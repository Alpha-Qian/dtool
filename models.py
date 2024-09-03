import asyncio,httpx,aiofiles
from asyncio import Task
import dtool
import time
import io

class Block:
    __slots__ = ('process','end','running')
    def __init__(self, process:int, end_pos:int, running:bool = False ,) -> None:
        self.process = process
        self.end = end_pos
        self.running = running

    

class BufferBlock(Block):
    def __init__(self, process: int, end_pos: int, running: bool = False) -> None:
        super().__init__(process, end_pos, running)
        self.buffer = bytearray()
        self.on_wait = False
def point_method(func):
    def warper(*arg, **kwarg):
        self_obj = arg[0]
        point_obj = self_obj._obj
        return func(*point_obj+arg[1:] , **kwarg)
class point(type):
    
class CircleIo:
    def __init__(self,size) -> None:
        self._size = size
        self._off = 0
        self._io = bytearray(size)

    def seek(self, off):
        self._off = off % self._size

    def write(self, data):
        size = len(data)
        if size > self._size:
            raise ValueError
        if size + self._off < self._size:
            self._io[self._off : self._off + size] = data
            self._off += size
        else:
            self._io[self._off: ] = data[ :self._size - self._off]
            self._io[ :self._off + size - self._size] = data[self._size - self._off: ]
            self._off += size - self._size

    def read(self, size):
        if size > self._size:
            raise ValueError
        if size
    async def pop(self):

        
    
    def read(self, size):
        return self._io[self._off]

    def tell(self):
        return self._io.tell()


class CircleStream():
    def __init__(self, size) -> None:
        self.size = size
        self._start = 0
        self._end = self._start + size
        self.data = bytearray(size)
    @property
    def start(self):
        return self._start
    @start.setter()
    def setter(self, value):
        self._start += value
        self._end += value
    
    @property
    def end(self):
        return self._end

    
    async def seek_and_write(self, pos, data):
        size = len(data)
        if size > self.size:
            raise ValueError
        if self.start == pos:
            self.start += size
        pos = pos % self.size
        if pos + size < self.size:
            self.data[pos:pos + size] = data
        else:
            self.data[pos: self.size] = data[:self.size - ]


        
    async def __anext__(self):
        pass
    async def __aiter__(self):
        return self
    
    async def pop(self)

class StreamGetter:
    def __init__(self,step) -> None:
        self.step = step
        self.process = 0
        self.speed_monitor = SpeedMonitor(self)
    async def __anext__(self):
        self.process += self.step
        next(self.speed_monitor)

class IoWriter:
    '将IO'
    def __init__(self,io :io.IOBase) -> None:
        self.io = io
    def __getitem__(self,key:int|slice):
        self.io.seek(key.start)
        return self.io.read(key.stop - key.start)
    def __setitem__(self,key:int|slice,value):
        self.io.seek(key.start)
        self.io.
    def __delitem__(self:int|slice,key):
        pass


class DataChunk():
    __slot__ = ('start','end','data')
    def __init__(self,start_pos) -> None:
        self.start = start_pos
        self.end = start_pos
    def __len__(self):
        return self.end - self.start
    def seek(self):
        pass
    def write(self):
        pass

class DataList():#模拟文件，记录写入信息
    def __init__(self):
        self._offset = 0
        self._list:list[DataChunk] = [] #[(0:start,1:end,2:data)*]
        self.insert_chunk = None
        self.seek(0)
    def __len__(self):
        pass
    def seek(self,offset:int):
        self._offset = offset
        for i in self._list:
            if offset < i.end:
                if i.start < offset:
                    self.insert_chunk = i
                else:
                    self._list.insert((new_chunk:=DataChunk(offset)),self._list.index(i))
                    self.insert_chunk = new_chunk
                return
        self._list.append(( new_chunk:=DataChunk(offset) ))
        self.insert_chunk = new_chunk
        
    def wirte(self,data:bytes):
        len_data = len(data)
        if self._offset
    def truncate(self,size = -1):
        pass
        
    def __iter__(self):
        return DataIter(self)
    def __next__(self):
        return self._list.pop(0)

class DataIter:
    def __init__(self,data:DataList) -> None:
        self.data_list = data
        self.offset = 0
        self.buffer=bytearray()
    def __next__(self):
        self.data_list
        

        


class TaskChunk:
    def __init__(self,start,end,task) -> None:
        self.start = start
        self.end = end
        self.task = task




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
        self._list[self.start_index(start_pos)].running = False

    
    def empty_chunk(self) -> list[Block]:
        chunks = []
        for i in range(len(self)):
            chunks.append( Block( self[i].end, self[i+1].start, self[i].running ))
    
    def unfinish_chunk(self) -> list[Block]:
        chunks = []
        for i in range(len(self)):
            if self[i].running == True:
                chunks.append( Block( self[i].end, self[i+1].start,True ) )#   允许self[i+1]原因见__getitem__
        return chunks
    
    def unplan_chunk(self) -> list[Block]:
        chunks = []
        for i in range(len(self)):
            if self[i].running == False:
                chunks.append( Block( self[i].end, self[i+1].start, False ) )
        return chunks

    def len_working_chunk(self) -> int:
        length = 0
        for i in self:
            if i.running == True:
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
    def __init__(self,mission:dtool.DownloadIO) -> None:
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
    
    def info(self) -> tuple:
        t = time.time()
        return (self.mission.process - self.process) / (t - self.time), (t - self.time)
    
    async def aget(self,second:int = 1):
        process = self.mission.process
        t = time.time()
        await asyncio.sleep(second)
        return (self.mission.process - process)/(time.time()-t)

class SpeedCacher:

    def __init__(self,mission,block_num = 0, threshold = 0.1, accuracy = 0.1) -> None:
        self.speed = 0
        self.old_speed = 0
        self.change_num:int = block_num
        self.mission:dtool.DownloadIO = mission
        self.monitor = SpeedMonitor(mission)
        self.max_speed_per_thread = 0
        self.threshold = threshold #判定阈值 >=0 <1 无量纲
        self.accuracy = accuracy #精确度 >=0 单位为秒 越大越精确但响应更慢 防止短时间内速率波动 除于秒数后等价于判定阈值

    def reset(self,block_num):
        self.speed = 0
        self.old_speed = 0
        self.max_speed_per_thread = 0
        self.change_num = block_num

    def change(self,change_num:int = 1):
        if change_num != 0:
            self.monitor.reset()
            self.old_speed = self.speed
            self.change_num = change_num

    def new_connect(self):
        if self.check:
            self.mission.re_divition_task()
            self.change()

    def get_speed(self):
        self.speed = next(self.monitor)
        return (self.speed - self.old_speed) / self.change_num
    
    def get(self):#old
        self.speed = next(self.monitor)
        if (i := self.speed/self.mission.task_num) > self.max_speed_per_thread:
            self.max_speed_per_thread = i
        return (self.speed - self.old_speed) / self.change_num /self.max_speed_per_thread
    
    def check(self) -> bool:#new
        self.speed, secend = self.monitor.info()
        if (i := self.speed/self.mission.task_num) > self.max_speed_per_thread:
            self.max_speed_per_thread = i
        if secend > 60:
            self.monitor.reset()
        return ((self.speed - self.old_speed) / self.change_num /self.max_speed_per_thread - self.threshold) > self.accuracy/secend




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
    
    async def confirm(self):
        await self._enter.acquire()
        self._exit.release()

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