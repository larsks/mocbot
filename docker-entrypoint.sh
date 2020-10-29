#!/bin/sh

if [ "$#" -eq 1 ] &&  "$1" = "sh" ]; then
	exec /bin/sh
fi

if [ "$(id -u)" -eq 0 ]; then
	chown -R supybot:supybot /app
	exec su-exec supybot $0 "$@"
fi

if ! [ -f supybot.conf ]; then
	python gen_config.py -o supybot.conf supybot.conf.in
fi

exec "$@"
