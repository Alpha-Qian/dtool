import asyncio

class TaskCoordinator:
    def __init__(self) -> None:
        self.arg = None
        self.result = None
        self._enter = asyncio.Lock()
        self._exit = asyncio.Lock()
        self._enter._locked = True #在unlock中释放，在enter中获取
        self._exit._locked = True #在exit中释放,在unlock中获取

    async def __aenter__(self):
        await self._enter.acquire()
        self.result = None
        return self.arg
    
    async def set_result(self, result):
        assert self._enter.locked
        self.result = result

    async def __aexit__(self,exc,excv,track):
        self._exit.release()

    async def unlock(self, arg = None):
        self._enter.release()
        self.arg = arg
        await self._exit.acquire()
        return self.result
    
    async def confirm(self):
        await self._enter.acquire()
        self._exit.release()


    def enter(self):
        return self.__aenter__()
    def exit(self,exc=None,excv=None,track=None):
        return self.__aexit__(exc,excv,track)

class Quene(asyncio.Queue):
    async def __aenter__(self):
        return await self.get()
    async def __aexit__(self, exc, exv, tb):
        self.task_done()
        return False