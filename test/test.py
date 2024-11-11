import sys
import asyncio
import aiofiles
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import dtool

url = 'https://dldir1.qq.com/qqfile/qq/QQNT/Windows/QQ_9.9.15_240822_x64_01.exe'

async def test_all():
    pass

async def test_all_file():
    pass

async def test_stream():
    return
    async with WebResouseStream(url) as stream:
        file = await aiofiles.open('stream_test.exe','wb')
        async for chunk in stream:
            print(f'{len(chunk)  }\t{stream._process,stream._file_size   }\t{chunk[-4:]   }')
            await file.write(chunk)
        await file.close()
        print('end')


asyncio.run(test_stream())



