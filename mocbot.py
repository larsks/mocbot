import asyncio
import bottom
import logging
import time

from dataclasses import dataclass

logging.basicConfig(level='DEBUG')

LOG = logging.getLogger(__name__)


@dataclass
class Ratelimit:
    interval = 1
    bucket = 4
    bucket_interval = 5

    count = 0
    last = 0

    def next(self):
        while True:
            now = time.time()

            if now - self.last >= self.bucket_interval:
                self.count = self.bucket

            if self.count:
                self.count -= 1
                break
            elif now - self.last > self.interval:
                break
            else:
                LOG.debug('ratelimiting')
                time.sleep(1)

        self.last = now


class Mocbot(bottom.Client):

    def __init__(self, nick=None, config=None, **kwargs):
        super().__init__(**kwargs)

        self._config = config
        self._ratelimit = Ratelimit()
        self.on('CLIENT_CONNECT', self.on_connect)

    def send(self, *args, **kwargs):
        self._ratelimit.next()
        super().send(*args, **kwargs)

    async def on_connect(self, **kwargs):
        nick = self._config['nick']

        LOG.info('identifying to irc')
        bot.send('NICK', nick=nick)
        bot.send('USER', user=nick, realname=nick)

        # Don't try to join channels until the server has
        # sent the MOTD, or signaled that there's no MOTD.
        done, pending = await asyncio.wait(
            [bot.wait("RPL_ENDOFMOTD"),
             bot.wait("ERR_NOMOTD")],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel whichever waiter's event didn't come in.
        for future in pending:
            future.cancel()

        for channel in self._config.get('channels', []):
            LOG.info(f'joining {channel}')
            bot.send('JOIN', channel=channel)

        LOG.info('starting announcer')
        asyncio.create_task(self.announcer())

    async def announcer(self):
        while True:
            now = time.ctime()

            LOG.info('announcing')
            for channel in self._config.get('channels', []):
                self.send('PRIVMSG',
                          target=channel,
                          message=f'The time is {now}')

                await asyncio.sleep(0.5)


config = {
    'nick': 'mocbot_dev',
    'channels': [
        '#oddbit',
        '#oddbit-dev',
    ],
}


bot = Mocbot(config=config,
             host='chat.freenode.net',
             port='6697',
             ssl=True)


loop = asyncio.get_event_loop()
loop.create_task(bot.connect())
loop.run_forever()