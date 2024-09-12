from rebuild import *
import rebuild
import asyncio

url = 'https://dldir1.qq.com/qqfile/qq/QQNT/Windows/QQ_9.9.15_240822_x64_01.exe'

async def stream():
    async with rebuild.WebResouseStream(url) as stream:
        async for i in stream:
            print(f'{len(i)  }\t{i[-4:]   }\t{stream.block_list[0]   }')
async def all():
    context = await rebuild.WebResouseAll(url)
async def file():
    WebResouseFile(url)
asyncio.run(stream())



