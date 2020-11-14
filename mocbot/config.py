import itertools
import os
import re
import yaml

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from typing import List, Optional

from mocbot.exceptions import ConfigurationError

DEFAULT_NICK = 'mocbot'
DEFAULT_HOST = 'chat.freenode.net'
DEFAULT_PORT = 6697
DEFAULT_SSL = True
DEFAULT_RECONNECT_DELAY = 10
DEFAULT_EVENT_SOCKET = 'tcp://127.0.0.1:1509'


class PatternObject:
    '''Calls re.compile on all regular expression patterns'''

    def __post_init__(self):
        product = itertools.product(['include', 'exclude'],
                                    ['repos', 'events'])
        for action, target in product:
            attrname = f'{action}_{target}'
            if hasattr(self, attrname):
                setattr(self, attrname, [
                    re.compile(pattern)
                    for pattern in getattr(self, attrname)
                ])


@dataclass_json
@dataclass
class Channel(PatternObject):
    '''Configuration for an individual channel.'''

    name: str = None
    include_repos: List[str] = field(default_factory=list)
    exclude_repos: List[str] = field(default_factory=list)
    include_events: List[str] = field(default_factory=list)
    exclude_events: List[str] = field(default_factory=list)


def truthy(val):
    '''Returns True for values that look truthy, False otherwise'''

    if hasattr(val, 'lower'):
        return val.lower() in ['yes', 'true', '1']
    else:
        return bool(val)


@dataclass_json
@dataclass
class Configuration(PatternObject):
    '''Main mocbot configuration.

    You may provide configuration information via environment variables,
    via a dictionary, or via a YAML configuration file.

    An example configuration file might look like this:

        ---
        mocbot:
          nick: mocbot_dev

          include_repos:
            - larsks/

          channels:
            - name: '#oddbit'
              include_events:
                - push
              exclude_repos:
                - larsks/boring
    '''

    nick: str = os.environ.get('MOCBOT_NICK', DEFAULT_NICK)
    nickserv_password: Optional[str] = os.environ.get('MOCBOT_NICKSERV_PASSWORD')

    host: str = os.environ.get('MOCBOT_HOST', DEFAULT_HOST)
    port: int = int(os.environ.get('MOCBOT_PORT', DEFAULT_PORT))
    ssl: bool = truthy(os.environ.get('MOCBOT_SSL', DEFAULT_SSL))

    reconnect_delay: int = int(os.environ.get('MOCBOT_RECONNECT_DELAY', DEFAULT_RECONNECT_DELAY))
    event_socket: str = os.environ.get('MOCBOT_EVENT_SOCKET', DEFAULT_EVENT_SOCKET)

    include_repos: List[str] = field(default_factory=list)
    exclude_repos: List[str] = field(default_factory=list)
    include_events: List[str] = field(default_factory=list)
    exclude_events: List[str] = field(default_factory=list)

    channels: List[Channel] = field(default_factory=list)

    @classmethod
    def from_config_file(cls, path, key=None):
        with open(path) as fd:
            data = yaml.safe_load(fd)

        try:
            config = data[key] if key else data
            return cls.from_dict(config)
        except KeyError:
            raise ConfigurationError(
                f'expecting top-level key "{key}"')
