import asyncio
import bottom
import jinja2
import json
import logging
import zmq
import zmq.asyncio

from mocbot.ratelimit import Ratelimit

LOG = logging.getLogger(__name__)
ENV = jinja2.Environment(
    loader=jinja2.ChoiceLoader([
        jinja2.FileSystemLoader('run/templates'),
        jinja2.FileSystemLoader('templates'),
        jinja2.PackageLoader('mocbot', 'templates'),
    ])
)


def events(*events):
    '''Decorator for setting a function's _irc_events attribute'''

    def wrapper(func):
        func._irc_events = events
        return func

    return wrapper


class Announcer:
    def __init__(self, bot):
        self.bot = bot
        self.loop_task = None
        self.ctx = zmq.asyncio.Context()

        asyncio.create_task(self.run())

    async def quit(self):
        self.loop_task.cancel()

    async def run(self):
        self.loop_task = asyncio.create_task(self.loop())
        await self.loop_task

    def make_socket(self):
        sock = self.ctx.socket(zmq.SUB)
        sock.subscribe('')
        sock.bind(self.bot.config.event_socket)

        return sock

    async def next_event(self, sock):
        event_class, event_data = await sock.recv_multipart()
        event_class = event_class.decode()
        event = json.loads(event_data)

        event_name = '{}:{}'.format(
            event_class,
            event.get('action', 'none')
        ).lower()

        if 'repository' in event:
            repo_name = event['repository']['full_name'].lower()
        else:
            repo_name = 'none/none'

        return repo_name, event_class, event_name, event

    def wants_event(self, channel, event_name, repo_name):
        LOG.debug('considering %s message for %s on channel %s',
                  event_name, repo_name, channel.name)

        include_events = self.bot.config.include_events + channel.include_events
        exclude_events = self.bot.config.exclude_events + channel.exclude_events
        include_repos = self.bot.config.include_repos + channel.include_repos
        exclude_repos = self.bot.config.exclude_repos + channel.exclude_repos

        want = False

        if any(pattern.match(event_name) for pattern in include_events):
            LOG.debug('found event in include_events')
            want = True

        if any(pattern.match(repo_name) for pattern in include_repos):
            LOG.debug('found repo in include_repos')
            want = True

        if any(pattern.match(event_name) for pattern in exclude_events):
            LOG.debug('found event in exclude_events')
            want = False

        if any(pattern.match(repo_name) for pattern in exclude_repos):
            LOG.debug('found repo in exclude_repos')
            want = False

        return want

    async def loop(self):
        LOG.info('starting announcer')
        sock = self.make_socket()
        config = self.bot.config

        try:
            while True:
                if not self.bot._connected:
                    LOG.debug('waiting for connection')
                    await asyncio.sleep(1)
                    continue

                repo_name, event_class, event_name, event = await self.next_event(sock)
                LOG.info('received %s event for %s', event_name, repo_name)

                try:
                    template = ENV.select_template([event_name, event_class])
                except jinja2.exceptions.TemplateNotFound:
                    LOG.warning('no template available for %s event', event_name)
                    continue

                msgs = template.render(event_name=event_name, event=event)
                LOG.debug('msgs = %s', msgs)

                for channel in config.channels:
                    if self.wants_event(channel, event_name, repo_name):
                        for msg in msgs.splitlines():
                            # don't send blank lines
                            if not msg:
                                continue

                            await self.bot.send('PRIVMSG',
                                                target=channel.name,
                                                message=msg)
        finally:
            LOG.debug('closing socket')
            sock.close()


class Mocbot(bottom.Client):

    def __init__(self, config):
        super().__init__(
            host=config.host,
            port=config.port,
            ssl=config.ssl,
        )

        self.config = config
        self.announcer = None
        self.ratelimit = Ratelimit()
        self._connected = False

        self.init_events()

    def init_events(self):
        '''Attach methods to irc events.

        This iterates through attributes of the current object,
        attaching them to irc events if they have an
        _irc_events attribute.
        '''

        for attrname in dir(self):
            attr = getattr(self, attrname)

            if hasattr(attr, '_irc_events'):
                for event in attr._irc_events:
                    LOG.debug('handle %s with %s', event, attr.__name__)
                    self.on(event, attr)

    async def send(self, *args, **kwargs):
        '''Send rate-limited irc messages'''

        await self.ratelimit.limit()
        LOG.debug('send args=%s, kwargs=%s', args, kwargs)
        super().send(*args, **kwargs)

    @events('PING')
    async def on_ping(self, message, **kwargs):
        await self.send('PONG', message=message)

    @events('CLIENT_DISCONNECT')
    async def on_disconnect(self, **kwargs):
        LOG.warning('disconnected from server. reconnect in %d seconds...',
                    self.config.reconnect_delay)
        self._connected = False

        await self.stop_announcer()

        await asyncio.sleep(self.config.reconnect_delay)
        asyncio.create_task(self.connect())

    @events('CLIENT_CONNECT')
    async def on_connect(self, **kwargs):
        nick = self.config.nick

        LOG.info('identifying to irc')
        await self.send('NICK', nick=nick)
        await self.send('USER', user=nick, realname=nick)

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

        for channel in self.config.channels:
            LOG.info(f'joining {channel.name}')
            await self.send('JOIN', channel=channel.name)

        self._connected = True
        self.start_announcer()

    def start_announcer(self):
        self.announcer = Announcer(self)

    async def stop_announcer(self):
        await self.announcer.quit()
        self.announcer = None
