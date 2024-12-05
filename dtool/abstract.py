from abc import ABC, abstractmethod
class AbstractDownloadBase(ABC):
    @abstractmethod
    def __init__(self) -> None:
        pass

    @abstractmethod
    def _init(self,response):
        pass
    
    def divition_task(self, times:int = 1):
        #非抽象方法

    @abstractmethod
    def start_block(self, block):
        pass

    @abstractmethod
    async def download(self,block):
        pass

    @abstractmethod
    async def main(self):
        pass
    
    @abstractmethod
    async def deamon(self, check_time):
        pass


class SaveBase(ABC):
    """如何处理下载内容的策略"""
    
    @abstractmethod
    async def _handle_chunk(self, chunk, chunck_size):
        raise NotImplementedError
    
    @abstractmethod
    async def _get_buffer(self, process, step):
        raise NotImplementedError
