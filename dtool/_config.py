from dtool.models import Inf


class Config:
    def __init__(
        self,
        pre_task,
        remain_time,
        remain_size,
    ) -> None:
        self.pre_task = pre_task
        self.remain_time = remain_time
        self.remain_size = remain_size


class ClientConfig:
    def __init__(
        self,
        max_mission_num,
        max_task,  # httpx.client的最大连接数
        max_task_num,
        config=Config(),
        auto=True,
    ) -> None:
        pass


class ControlConfig:
    def __init__(
        self,
        max_task=64,
        flush_time=1,
        threshold=0.1,
        accuracy=0.1,
        turple=((0.7, 3), (0.5, 2), (0.1, 1)),
    ) -> None:
        pass


DEFAULTCONFIG = Config()
DEFAULTCLIENTCONFIG = ClientConfig(config=DEFAULTCONFIG)
DEFAULTCONTROLCONFIG = ControlConfig(turple=((0.1, 1)))


FORCE = True  # jump over
SECREAT = False  # raise exception
INGONE = None

"""
注意区分: start, process, stop, end, buffer_stop, buffering等

0 <= start <= stream_process <= stop <= end = file_size
process + buffering = buffer_stop 
control_end = min(buffer_stop, stop)
process <= stop - start

0:  索引开始的地方
start:  从这里开始请求资源,如果不允许续传start之前的数据会丢弃
process:    下载的总字节数
stream_process: buffer开始处
stop:   和block.stop相同,是stream函数主动截断的位置
end:    资源末尾位置,由服务器截断,stop > end会警告
control_end:    不会在此位置之后创建连接
buffer_stop:    stream的download函数运行在此会等待

pre_divition:   在start 和 stop间划分
re_divition: 根据blocklist在control前划分
"""
