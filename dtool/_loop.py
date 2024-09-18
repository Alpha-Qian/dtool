from selectors import BaseSelector
import asyncio
asyncio.BaseEventLoop
class Loop(asyncio.SelectorEventLoop):
    def __init__(self, selector: BaseSelector | None = None) -> None:
        super().__init__(selector)
        self.on_stop_time = self.time()

    def run_forever(self) -> None:
        self.on_stop_time += self.time() - self.stoping_time
        super().run_forever()

    def stop(self) -> None:
        self.stoping_time = self.time()
        super().stop()
    
    def run_time(self):
        return self.time() - self.on_stop_time
    
    def run_sec(self, secend:float):
        self.run_forever()
        self.call_later(secend, self.stop)
        self.


