import httpx
import asyncio
import time


class RateLimitedStream(httpx.AsyncByteStream):
    def __init__(self, stream: httpx.AsyncByteStream, rate_limit: int):
        """
        :param stream: 原始响应流
        :param rate_limit: 每秒允许的最大字节数 (Bytes per second)
        """
        self._stream = stream
        self._rate_limit = rate_limit  # 限速，单位：字节/秒

    async def aclose(self):
        await self._stream.aclose()

    async def aread(self, size: int) -> bytes:
        chunk = await self._stream.aread(size)
        if not chunk:
            return chunk

        # 限制速度：计算延迟时间
        delay = len(chunk) / self._rate_limit
        await asyncio.sleep(delay)
        return chunk


class RateLimitedTransport(httpx.AsyncBaseTransport):
    def __init__(self, transport: httpx.AsyncBaseTransport, rate_limit: int):
        """
        :param transport: 原始传输层
        :param rate_limit: 每秒允许的最大字节数
        """
        self._transport = transport
        self._rate_limit = rate_limit

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._transport.handle_async_request(request)

        # 用自定义流包装原始响应流
        response.stream = RateLimitedStream(response.stream, self._rate_limit)
        return response


class DtoolClient(httpx.AsyncClient):
    pass

class SpeedLimitChecker:
    pass