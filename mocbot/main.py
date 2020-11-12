import asyncio
import click
import logging
import os
import sys

from mocbot.bot import Mocbot
from mocbot.exceptions import ApplicationError

LOG = logging.getLogger(__name__)


@click.command()
@click.option('--config-file', '-f', default='mocbot.yml')
@click.option('--verbose', '-v', count=True)
def main(config_file, verbose):
    try:
        loglevel = ['ERROR', 'WARNING', 'INFO', 'DEBUG'][verbose]
    except IndexError:
        loglevel = 'DEBUG'

    logging.basicConfig(level=loglevel)

    try:
        bot = Mocbot.from_config_file(config_file)

        loop = asyncio.get_event_loop()
        loop.create_task(bot.connect())
        loop.run_forever()
    except ApplicationError as err:
        raise click.ClickException(str(err))


def web():
    os.execvp('gunicorn',
              ['gunicorn'] + sys.argv[1:] + ['mocbot.web:app'])
