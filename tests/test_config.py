import pytest
import yaml

from io import StringIO
from unittest import mock

import mocbot.config


def test_default_config():
    conf = mocbot.config.Configuration()

    assert conf.nick == mocbot.config.DEFAULT_NICK
    assert conf.host == mocbot.config.DEFAULT_HOST
    assert conf.port == mocbot.config.DEFAULT_PORT
    assert conf.ssl == mocbot.config.DEFAULT_SSL
    assert conf.reconnect_delay == mocbot.config.DEFAULT_RECONNECT_DELAY
    assert conf.event_socket == mocbot.config.DEFAULT_EVENT_SOCKET


def test_config_from_dict():
    data = {
        'nick': 'test',
        'host': 'test',
        'port': 1234,
    }
    conf = mocbot.config.Configuration.from_dict(data)

    assert conf.nick == data['nick']
    assert conf.host == data['host']
    assert conf.port == data['port']


def test_config_from_file():
    data = {
        'nick': 'test',
        'host': 'test',
        'port': 1234,
    }

    buf = StringIO()
    yaml.safe_dump(data, buf)
    buf.seek(0)

    with mock.patch('mocbot.config.open') as mock_open:
        mock_open.return_value = buf
        conf = mocbot.config.Configuration.from_config_file(path='/test')

    assert conf.nick == data['nick']
    assert conf.host == data['host']
    assert conf.port == data['port']


def test_config_channel():
    data = {
        'channels': [
            {
                'name': '#test',
                'include_repos': [
                    'test/',
                ],
            },
        ]
    }

    conf = mocbot.config.Configuration.from_dict(data)

    assert len(conf.channels) > 0
    assert conf.channels[0].name == '#test'


def test_regex_compile():
    data = {
        'channels': [
            {
                'name': '#test',
                'include_repos': [
                    'test/',
                ],
            },
        ]
    }

    conf = mocbot.config.Configuration.from_dict(data)

    assert len(conf.channels) > 0
    assert len(conf.channels[0].include_repos) > 0
    assert conf.channels[0].include_repos[0].match('test/pattern')
