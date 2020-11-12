import asyncio
import bottom
import json
import logging
import time
import yaml
import zmq
import zmq.asyncio

from dataclasses import dataclass

from mocbot.exceptions import ConfigurationError

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

    def __init__(self, config=None, **kwargs):
        super().__init__(**kwargs)

        self._config = config
        self._ratelimit = Ratelimit()

        self.init_zmq()
        self.init_events()

    @classmethod
    def from_config_file(cls, path):
        with open(path) as fd:
            data = yaml.safe_load(fd)

        try:
            config = data['mocbot']

            return cls(
                config=config,
                host=config['host'],
                port=int(config.get('port', '6667')),
                ssl=config.get('ssl'),
            )
        except KeyError:
            raise ConfigurationError('missing required configuration values')

    def init_events(self):
        self.on('CLIENT_CONNECT', self.on_connect)

    def init_zmq(self):
        sock_uri = self._config.get('zmq_socket_uri', 'tcp://127.0.0.1:1509')
        self.ctx = zmq.asyncio.Context()
        self.zs = self.ctx.socket(zmq.SUB)
        self.zs.subscribe('')
        self.zs.bind(sock_uri)

    def send(self, *args, **kwargs):
        self._ratelimit.next()
        super().send(*args, **kwargs)

    async def on_connect(self, **kwargs):
        nick = self._config['nick']

        LOG.info('identifying to irc')
        self.send('NICK', nick=nick)
        self.send('USER', user=nick, realname=nick)

        # Don't try to join channels until the server has
        # sent the MOTD, or signaled that there's no MOTD.
        done, pending = await asyncio.wait(
            [self.wait("RPL_ENDOFMOTD"),
             self.wait("ERR_NOMOTD")],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel whichever waiter's event didn't come in.
        for future in pending:
            future.cancel()

        for channel in self._config.get('channels', {}):
            LOG.info(f'joining {channel}')
            self.send('JOIN', channel=channel)

        LOG.info('starting announcer')
        asyncio.create_task(self.announcer())

    async def announcer(self):
        while True:
            event_type, event_data = await self.zs.recv_multipart()
            event_type = event_type.decode()
            event_data = json.loads(event_data)
            LOG.info('received %s event', event_type)

            for channel in self._config.get('channels', []):
                self.send('PRIVMSG',
                          target=channel,
                          message=f'Received {event_type} message')
