import asyncio, typing
from rebuild import *

def get(url) -> bytearray:
    WebResouseAll(url)

def stream(url, buffer_size = -1) -> typing.AsyncIterable:
    return WebResouseStream(url, buffer_size)
for i in stream(url=) :
    pass


def save(url, path = None, file_name = None):
    WebResouseFile(url)

def stream_and_save():
    pass
def res_io():
    pass