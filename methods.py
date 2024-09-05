import time, asyncio
async def loop_speed_test():
    t = time.time()
    while 1:
        await asyncio.sleep(0)
        t2 = time.time()
        print(f'{t2 - t}')
        t = t2
