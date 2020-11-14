import asyncio
import logging
import time

from dataclasses import dataclass

LOG = logging.getLogger(__name__)


@dataclass
class Ratelimit:
    '''Await on a Ratelimit object to rate limit things.

    Allows burts of up to <bucket> events. After the bucket is empty,
    events are limited to 1 every <interval> seconds. Bucket refills
    after <bucket_interval> seconds.
    '''

    interval: int = 1
    bucket: int = 5
    bucket_interval: int = 10

    count = 0
    last = 0

    async def limit(self):
        while True:
            now = time.time()
            delta = now - self.last

            if delta >= self.bucket_interval:
                self.count = self.bucket

            LOG.debug('bucket %s count %s delta %s',
                      self.bucket, self.count, delta)
            if self.count:
                self.count -= 1
                break
            elif delta > self.interval:
                break
            else:
                LOG.debug('ratelimiting')
                await asyncio.sleep(1)

        self.last = now