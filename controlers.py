



class Controler:
    def __init__(self) -> None:
        self.web_resouse = None
        self.block_list = []
    def cut_block(self, tg, start_pos:int, end_pos:int|None = None):
        '''自动根据开始位置创建新任务,底层API'''
        if len(self.block_list) > 0 and start_pos < self.block_list[-1].end:
            for block in self.block_list:
                if block.process < start_pos < block.end:
                    new_block = Block(start_pos, block.end) #分割
                    block.end = start_pos
                    self.block_list.insert(self.block_list.index(block)+1,new_block)
                    self.task_group.create_task(self.connect(new_block))
                    return
            raise Exception('重复下载')
            if end_pos is not None:
                new_block = ConnectBase(start_pos, end_pos, self)
                self.block_list
        else:
            new_block = self.new_block(start_pos, self.res_size)
            self.block_list.append(new_block)
            self.task_group.create_task(self.connect(new_block))
    def pre_dividion(self, )