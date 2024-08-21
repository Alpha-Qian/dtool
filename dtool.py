import aiofiles
import aiofiles.base
import asyncio, httpx, aiofiles
from asyncio import Event,Lock
import pathlib
import pickle
import time
import models

class DownControler:#改为多文件下载控制
    '''self.max_connect'''
    def __init__(self,max_connect=32) -> None:
        self.max_connect = max_connect
        self.connect_num = 0
        self.speed_list :list[int]= []#统计在不同连接数下的链接速度
    
    async def speed_statistic(self):
        pass

    async def new_url(self,url,path):
        pass

    async def download(self):
        down_file = self.down_file
        controler = asyncio.create_task(self.down_control())
        await asyncio.create_task(down_file.get_headers())
        if down_file.accept_range:
            await asyncio.create_task(down_file.download_main())
        else:
            pass
        #controler.cancel()
        await controler
    
    async def monitor(self):
        len_task = len(self.down_file.task_group)
        len_sem = self.down_file.sem._value
    
    async def down_control(self,contr_func):
        download_file = self.down_file
        sem = download_file.sem
        self.task_group = download_file.task_group
        while 1:
            sem._value

    async def get_data_chunk(self):
        return zip(self.down_file.start_list,self.end_list)
    async def get_empty_chunk(self):
        return zip(self.down_file.end_list[:-1],self.start_list[1:])

    async def get_speed(self,time):
        size1 = self.down_file.downed_size
        asyncio.sleep(time)
        return (self.down_file.downed_size - size1)/time
    async def speed_monitor(self,time):
        pass
    async def restart(self):
        pass
    async def stop(self):
        pass

class DownloadFile:
    client = httpx.AsyncClient()

    def __init__(self, url, path, min_task_num = 1,auto = True, max_task_num =32):
        self.url = url
        self.path = path
        self.filename = url.split('/')[-1]

        self.file_lock = asyncio.Lock()
        self.download_prepare = models.TaskCoordinator()
        self.saved_info:bool = False
        self.accept_range = None
        self.file_size = 1
        self.process = 0
        self.task_list:list[DownBlocks] = []
        self.done_list:list[DownBlocks] =[]
        
        self.speed_static = models.SpeedStatis(self)
        self.task_num = 0
        self.min_task_num = min_task_num
        self.auto = auto
        self.target_task_num = min_task_num
        self.max_task_num = max_task_num

    def pre_cut_block(self,  block_num) -> range:
        block_size = self.file_size // block_num
        return range(block_num, block_size, self.file_size)
    
    def re_cut_block(self) -> int:
        if self.target_task_num < self.task_num or (self.file_size - self.process) / self.speed_static.monitor.get() < 3:#秒
            return
        if self.speed_static.cheek():
            self.target_task_num += 1
            self.speed_static.change(self.target_task_num)
        max_remain = 0
        for i in self.task_list:
            if i.end - i.process > max_remain:
                max_remain = i.end - i.process
                max_remain_Block:DownBlocks = self.task_list[i]
        if max_remain <= 1048576: #1MB
            return
        start_pos = (max_remain_Block.process + max_remain_Block.end) // 2
        self.new_task(start_pos)

    def new_task(self, start_pos):
        '''自动对新任务进行分割'''
        for block in self.task_list:
            if block.process < start_pos < block.end:
                new_block = DownBlocks(start_pos, block.end, self) #分割
                block.end = start_pos
                self.task_list.insert(self.task_list.index(block)+1,new_block)
                asyncio.create_task(new_block.run())
                self.speed_static.change(len(self.task_list))
                return
        new_block = DownBlocks(start_pos, self.file_size, self)
        self.task_list.append(new_block)
        asyncio.create_task(new_block.run())
        self.speed_static.change(len(self.task_list))
        
        
    async def main(self):
        self.new_task(0)
        async with self.download_prepare:
            if 'contect-length' in self.headers:
                self.file_size = int(self.headers['content-length'])
                self.accept_range = 'accept-ranges' in self.headers
            else:
                self.file_size = 1
                self.accept_range = False
            self.task_list[0].end = self.file_size - 1
            self.file = await aiofiles.open(self.filename,'w+b')
            self.saved_info = True
            for i in self.pre_cut_block(self.min_task_num):
                self.new_task(i)
        try:
            while 1:
                asyncio.sleep(1)
                if stac.check() and self.auto and len(self.task_list) < self.max_task_num:
                    self.new_task()
                    stac.change(len(self.task_list))
                
        except:
            for i in self.task_list:
                i.cancel()
        else:
            pass
        finally:
            for i in self.task_list:
                await i

            await self.file.close()


    


class DownBlocks():
    client = httpx.AsyncClient()
    def __init__(self, start, end, mission:DownloadFile):
        self.process = start
        self.end = end
        self.done = False
        self.running = False
        self.mission = mission

    async def run(self):
        self.task = asyncio.current_task()
        mission = self.mission
        mission.task_num += 1
        self.done = False
        try:
            if mission.saved_info:
                headers = {"Range": f"bytes={self.start}-{mission.file_size-1}"}
            async with self.client.stream('GET',mission.url,headers = headers) as response:
                if not mission.saved_info:
                    mission.headers = response.headers
                    mission.download_prepare.unlock()

                async for chunk in response.aiter_raw(16834):   #<--待修改以避免丢弃多余的内容
                    len_chunk = 16834
                    if self.process + len_chunk < self.end:
                        async with mission.file_lock:
                            await mission.file.seek(self.process)
                            await mission.file.write(chunk)
                        self.process += len_chunk
                    else:
                        chunk = chunk[: self.end - self.process]
                        len_chunk = len(chunk)
                        

                        async with mission.file_lock:
                            await mission.file.seek(self.process)
                            await mission.file.write(chunk)
                            if (i := mission.task_list.index(self) + 1) != len(mission.task_list
                            ) and mission.task_list[i].process > self.process + len_chunk:
                                i = await mission.file.read(self.process + len_chunk - self.end)#
                                if i != chunk[self.end - self.process:]:
                                    raise Exception('校验失败')
                        self.process = self.end
        except asyncio.exceptions.CancelledError:
            pass
        except httpx.TimeoutException:
            pass
        except Exception:
            pass
        else:
            mission.task_num -= 1
            mission.re_cut_block()
        finally:
            pass
    async def __await__(self):
        await self.task

    async def cancel(self):
        self.task.cancel()

async def main():
    #url = 'https://' + input('https://')
    url='https://f-droid.org/repo/com.termux_1000.apk'
    await asyncio.create_task(DownloadFile(url,path='./').main())
if __name__ =='__main__':
    asyncio.run(main())
    print('end')
