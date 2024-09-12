import asyncio,httpx,aiofiles
from asyncio import Task
import dtool
import time
import io
import enum
import typing

class DataUnit(enum.IntEnum):
    B = 1
    KB = 1024


class TimeUnit(enum.IntEnum):
    s = 1
    m = 60
    h = 60 * m
    d = 24 * h
class UnaccpetRangeError(Exception):
    pass

class SyncRunner:
    loop = None
    def sync_run(coro:typing.Coroutine):
        if not loop:
            loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)
    
    
from rebuild import Block
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
    
class StreamCon:
    def __init__(self) -> None:
        self.block_list = 1
        self._start =1
        self._end = 1
        self.step = 1
        self.wait_download = asyncio.Event()
        self.wait_iter = asyncio.Event()
    
    async def download(self, block):
        assert block in self.block_list
        while True:
            len_chunk = len(chunk)
            #wait iter
            while block.process + len_chunk > self.end:
                self.wait_iter.clear()
                await self.wait_iter.wait()

            #write
            yield 

            #call iter  暂时没有结束检测
            if block == self.block_list[0] and block.process + len_chunk > self.start + self.step :
                self.wait_download.set()

    async def iter(self):
        while True:
            if self.start + self.step > self.block_list[0].process:
                self.wait_download.clear()
                await self.wait_download.wait()

            yield
            self.start += self.step
        
            #call download
            self.wait_iter.set()


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
        if size + self._off < self._size:
            i = bytes(self._io[self._off : self._off + size])
            self._off += size
            return i
        else:
            i = bytes(self._io[self._off:] + self._io[:self._off + size - self._size])
            return i

        
    def tell(self):
        return self._io.tell()




class CircleStream():
    def __init__(self, size, block_list:list, step = 1024 ** 2) -> None:
        self.size = size
        self.block_list = block_list
        self._start = 0
        self._end = self._start + size
        self.step = step
        self._io = CircleIo(size)

        self.wait_download = asyncio.Event()
        self.wait_iter = asyncio.Event()
        self.wait_download.set()
        self.wait_iter.set()
    @property
    def start(self):
        return self._start
    @start.setter
    def start(self, value):
        self._start += value
        self._end += value
    
    @property
    def end(self):
        return self._end

    
    async def seek_and_write(self, pos, data):
        if pos + len(data) > self.end:
            self.wait_iter.clear()
            await self.wait_iter.wait()

        self._io.seek(pos)
        self._io.write(data)
        
        if self.block_list[0].process > self.start + 1024:
            self.wait_download.set()

    async def __anext__(self):
        if self.start + self.step > self.block_list[0].process:
            self.wait_download.clear()
            await self.wait_download.wait()
        
        self._io.seek(self.start)
        i = self._io.read(self.step)

        self.wait_iter.set()
        self.start += self.step
        
        return i
    
    async def __aiter__(self):
        return self
    

class CricleFile:
    def __init__(self) -> None:
        self._file = aiofiles.tempfile.TemporaryFile('w+b')
    async def __aenter__(self):
        return await self
    async def __await__(self):
        await self._file
    async def __aexit__(self):
        self



class StreamControl:
    def __init__(self, block_list) -> None:
        self.block_list = block_list
        self.iter_step = 1024
        self.download_step = 163840

        self._wait_download = asyncio.Event()
        self._wait_iter = asyncio.Event()
        self._wait_download.set()
        self._wait_iter.set()
    async def iter(self, pos):
        if self.block_list[0].process < self.start:
            self._wait_download.clear()
            await self._wait_download.wait()
        self._wait_iter.set()
    async def download(self, pos):
        if self.end < pos:
            self._wait_iter.clear()
            await self._wait_iter.wait()
        else:
            return




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
        #self.io.
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
        if self._offset:
            pass
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
    def __init__(self, mission, attr_name = 'process') -> None:
        self._obj = mission
        self._attr_name = attr_name
        self.process_cache = self.process
        self.time = time.time()

    @property
    def process(self):
        return getattr(self._obj, self._attr_name)
    
    def __next__(self):
        old_process = self.process_cache
        old_time = self.time
        self.process_cache = self.process
        self.time = time.time()
        return (self.process_cache - old_process) / (self.time - old_time) 
    
    def reset(self,):
        self.process_cache = self.process
        self.time = time.time()

    def get(self):
        time.sleep(1)
        return (self.process - self.process_cache) / (time.time() - self.time)
    
    def info(self) -> tuple:
        t = time.time()
        return (self.process - self.process_cache) / (t - self.time), (t - self.time)
    
    async def aget(self,second:int = 1):
        process = self.process
        t = time.time()
        await asyncio.sleep(second)
        return (self.process - process) / (time.time()-t)

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
        

class Inf:
    __slot__ = ()
    def __ne__(self, value: object) -> bool:
        '''return self == other'''
        return value is Inf
    def __gt__(self, other):
        '''return self > other'''
        return True
    def __lt__(self, other):
        '''retrun self < other'''
        return False
    
    def __gn__(self,other):
        '''return self >= other'''
        return self > other or self == other
    def __ln__(self, other):
        '''return self <= other'''
        return self < other or self == other
    
    def __add__(self, other):
        '''return self + other'''
        return self
    def __radd__(self, other):
        return self
    def __sub__(self, other):
        '''return self - other'''
        return self
    def __rsub__(self, other):
        return self
    def __str__(self) -> str:
        return ''
    



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



