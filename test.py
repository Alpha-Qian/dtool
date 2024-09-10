from rebuild import *
import asyncio


async def main():
    url = 'https://dldir1.qq.com/qqfile/qq/QQNT/Windows/QQ_9.9.15_240822_x64_01.exe'
    async with WebResouseStream(url) as stream:
        async for i in stream:
            print(len(i))
asyncio.run(main())
