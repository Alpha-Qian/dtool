import asyncio
import aiofiles
from dtool import *
import abc
import collections
url = 'https://dldir1.qq.com/qqfile/qq/QQNT/Windows/QQ_9.9.15_240822_x64_01.exe'

async def stream():
    async with WebResouseStream(url) as stream:
        file = await aiofiles.open('stream_test.exe','wb')
        test_set = set()
        async for chunk in stream:
            print(f'{len(chunk)  }\t{stream._process,stream._file_size   }\t{chunk[-4:]   }')
            #assert chunk[-8:] not in test_set
            #test_set.add(chunk[-8:])
            await file.write(chunk)
        await file.close()
        print('end')



class Test:
    pass
async def miao():
    pass
miao().__await__()

asyncio.run(stream())



