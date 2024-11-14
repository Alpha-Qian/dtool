import asyncio, httpx
from . import dtool


class Downloader:
    def __init__(self, cookies, headers):
        self.mission = httpx.AsyncClient(cookies=cookies, headers=headers)

    def new_task(self, url, headers={}):
        pass
