###
# Copyright (c) 2020, larsks
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import jinja2
import json
import os
import re
import threading
import zmq

from supybot.commands import (wrap, additional)  # NOQA
from supybot import callbacks
from supybot import conf
from supybot import ircdb
from supybot import ircmsgs
from supybot import log
from supybot import world


env = jinja2.Environment(
    loader=jinja2.PackageLoader(__name__)
)

github_conf = conf.supybot.plugins.get('Github')

sock_uri = os.environ.get('GH_SOCKET_URI', 'ipc:///run/github/github.sock')


def handle_event(event_name, event):
    try:
        template = env.get_template(event_name)
    except jinja2.exceptions.TemplateNotFound:
        log.warning('no template available for %s event', event_name)
        return

    msgs = template.render(event_name=event_name, event=event)
    event_action = '{}:{}'.format(
        event_name,
        event.get('action', '')
    ).lower()
    repo_name = event['repository']['full_name'].lower()

    for irc in world.ircs:
        for channel in irc.state.channels:
            log.info('considering %s message for %s to %s',
                     event_action, repo_name, channel)

            include_events = github_conf.get('include_events').get(channel).value.strip().lower()
            exclude_events = github_conf.get('exclude_events').get(channel).value.strip().lower()

            include_repos = github_conf.get('include_repos').get(channel).value.strip().lower()
            exclude_repos = github_conf.get('exclude_repos').get(channel).value.strip().lower()

            if exclude_events and any(re.match(pattern, event_action) for pattern in exclude_events.split(',')):
                log.info('not delivering message to %s: %s in exclude_events',
                         channel, event_name)
                continue

            if not any(re.match(pattern, event_action) for pattern in include_events.split(',')):
                log.info('not delivering message to %s: %s not in include_events',
                         channel, event_name)
                continue

            if exclude_repos and any(re.match(pattern, repo_name) for pattern in exclude_repos.split(',')):
                log.info('not delivering message to %s: %s in exclude_repos',
                         channel, repo_name)
                continue

            if not any(re.match(pattern, repo_name) for pattern in include_repos.split(',')):
                log.info('not delivering message to %s: %s not in include_repos',
                         channel, repo_name)
                continue

            log.info('delivering %s message for %s to %s',
                     event_action, repo_name, channel)
            for msg in msgs.splitlines():
                if not msg:
                    continue
                irc.queueMsg(ircmsgs.privmsg(channel, msg))


class QueueManager(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stats = {'total': 0}

    def run(self):
        log.info('start queue manager')
        self.ctx = ctx = zmq.Context()
        self.sock = sock = ctx.socket(zmq.SUB)
        sock.bind(sock_uri)
        sock.subscribe('')

        while True:
            event_name, event_data = sock.recv_multipart()
            event_name = event_name.decode()
            log.info('received %s message', event_name)

            self.stats[event_name] = self.stats.get(event_name, 0) + 1
            self.stats['total'] += 1

            event = json.loads(event_data)
            handle_event(event_name, event)


class Github(callbacks.Plugin):
    '''Handle github webhooks'''
    threaded = True

    def __init__(self, irc):
        super().__init__(irc)
        self.qm = QueueManager()
        self.qm.start()

    def ghstats(self, irc, msg, args):
        '''Return some basic statistics

        Nothing to see here
        '''

        irc.reply(json.dumps(self.qm.stats))

    def ghreset(self, irc, msg, args):
        '''Reset the statistics counters

        Nothing to see here
        '''

        if not ircdb.checkCapability(msg.prefix, 'admin'):
            irc.reply('This command is only available to admins')
            return

        self.qm.stats = {'total': 0}
        irc.reply('Reset counters')


Class = Github
