import asyncio
import time

import mocbot.ratelimit


def test_ratelimit():
    limit = mocbot.ratelimit.Ratelimit(interval=2, bucket=2)

    async def producer():
        await limit.limit()

    t_start = time.time()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(producer())
    t_end = time.time()

    delta = t_end - t_start
    assert limit.count == 1
