import asyncio, functools
asyncio.Runner

class SyncWarp:
    def __init__(self) -> None:
        self.loop = asyncio.get_event_loop()

    def warper(self, coro):
        def warper(*arg, **kwarg):
            return self.loop.run_until_complete(self.loop.create_task(coro))
        return warper
    
    def close(self):
        self.loop.stop()
        self.loop.close()

class SyncWarp(asyncio.Runner):
    def warp(self, coro):
        @functools.wraps(coro)#待修改...
        def warper(*arg, **kwarg):
            return self.run(coro(*arg, **kwarg))
        return warper

DEFAULTSYNCWARP = SyncWarp()
