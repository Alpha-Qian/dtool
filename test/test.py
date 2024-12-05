import sys
import asyncio
import aiofiles
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import dtool.dtool as dtool

url = 'https://dldir1.qq.com/qqfile/qq/QQNT/Windows/QQ_9.9.15_240822_x64_01.exe'

async def main():
    await test_bytebuffer()

async def test_base():
    pass

async def test_stream():
    pass

async def test_buffer():
    pass

async def test_bytebuffer():
    async for i in dtool.CircleByteBuffer(url):
        print(i)

asyncio.run(main())



