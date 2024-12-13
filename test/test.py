import sys
import asyncio
import aiofiles
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import dtool.dtool as dtool

url = 'https://dldir1.qq.com/qqfile/qq/QQNT/Windows/QQ_9.9.15_240822_x64_01.exe'

async def main():
    await test_file()



async def test_base():
    pass

async def test_file():
    await dtool.FileBase(url).main()

async def test_bytebuffer():
    async with dtool.ByteBuffer(url) as stream:
        print("inited")
        async for i in stream:
            print(len(i))


asyncio.run(main())



