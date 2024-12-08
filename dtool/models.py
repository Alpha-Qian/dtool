import asyncio
import numbers
import httpx
import re
import urllib
from numbers import Number
from time import time, monotonic
from collections import deque
from enum import Enum, StrEnum, IntEnum, auto
from email.utils import decode_rfc2231
from .dtool import Block
class ByteEnum(IntEnum):
    B = 1
    KB = 1024 * B
    MB = 1024 * KB
    GB = 1024 * MB
    TB = 1024 * GB
    PB = 1024 * TB
    EB = 1024 * PB
    ZB = 1024 * EB
    YB = 1024 * ZB

class Head(StrEnum):
    ACCEPT_RANGES = "accept-ranges"
    CONTENT_RANGES = "content-ranges"
    CONTENT_LENGTH = "content-length"
    CONTENT_TYPE = "content-type"
    CONTENT_DISPOSITION = "content-disposition"
    RANGES = "ranges"

class Query(StrEnum):
     RESPONSE_CONTENT_DISPOSITION = "response-content-disposition"



class ResponseHander:
    def __init__(self, response:httpx.Response) -> None:
        self.response = response
        self.request = response.request
    
    def check_response(self, block:Block):
        if Head.RANGES in self.response.headers:
            assert self.response.status_code == httpx.codes.PARTIAL_CONTENT
            assert f"bytes {block.start}-{block.stop-1}" in self.response.headers[Head.CONTENT_RANGES]
    def get_filename(self):
        pass

    def get_length(self):
        pass

class SpeedRecoder:
    def __init__(self, process = 0):
        self.process = process
        self.start_time = time()

    def reset(self, process):
        self.process = process
        self.start_time = time()

    def flash(self, process):
        
        d_time = time() - self.start_time
        speed = (process - self.process) / (d_time)
        return SpeedInfo(speed, d_time)
    
class BufferRecoder:
    def __init__(self,process = 0,/, buffering = 0):
        self.deque = deque(buffering)

    def put(self, process):
        self.deque.appendleft((process, time()))

    def get(self, process):
        t = self.deque[-1]
        return SpeedInfo(process - t[0], time() - t[1])
        

class SpeedInfo:
    __slot__ = ("speed", "time", "process")

    def __init__(self, dprocess, dtime) -> None:
        self.process = dprocess
        self.time = dtime
        if dtime != 0:
            self.speed = dprocess / dtime
        else:
            self.speed = 0


class TimeUnit(IntEnum):
    s = 1
    m = 60
    h = 60 * m
    d = 24 * h

numbers.
class Inf:

    __slot__ = ()
    def check_type(self, value):
        pass

    def __hash__(self):
        return hash(self.__class__)
    
    def __eq__(self, value: object) -> bool:
        """return self == other"""
        return value is Inf

    def __gt__(self, other):
        """return self > other"""
        return True

    def __lt__(self, other):
        """retrun self < other"""
        return False

    def __gn__(self, other):
        """return self >= other"""
        return self > other or self == other

    def __ln__(self, other):
        """return self <= other"""
        return self < other or self == other

    def __add__(self, other):
        """return self + other"""
        return self

    def __radd__(self, other):
        return self

    def __sub__(self, other):
        """return self - other"""
        if isinstance(other, Inf):
            raise ValueError("Cannot subtract Inf from anything")
        else:
            return self

    def __rsub__(self, other):
        raise ValueError("Cannot subtract Inf from anything")


    def __str__(self) -> str:
        return "UnKonwnSize"

class Bool:#UnKonwnType
    __slot__ = ('state')
    def __init__(self, state = None) -> None:
        self.state = state

    def _not(self):
        if self.state is None:
            return Bool(None)
        else:
            return Bool(not self.state)
        
    def __bool__(self):
        raise NotImplementedError()
    
    def bool(self, default:bool):
        if self.state is None:
            return default
        else:
            return bool(self.state)

    def __eq__(self, value):
        if not isinstance(value, Bool):
            value = Bool(value)
        if self.state is None or value.state is None:
            return Bool(None)
        else:
            return Bool(self.state == value.state)
        
    def __or__(self, value):
        if not isinstance(value, Bool):
            value = Bool(value)
        if self.state is None and value.state is None:
            return Bool(None)
        else:
            return Bool(self.state or value.state)
    
    def __and__(self, value):
        if not isinstance(value, Bool):
            value = Bool(value)
        if self.state is None or value.state is None:
            return Bool(None)
        else:
            return Bool(self.state and value.state)
    def __str__(self):
        return self.state.__str__()
a = Bool(None)
b = Bool(True)
c = a or b
print(c.state)
Unkownsize = Inf()
