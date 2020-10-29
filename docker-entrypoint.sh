#!/bin/sh

if [ "$#" -eq 1 ] &&  "$1" = "sh" ]; then
	exec /bin/sh
fi

if [ "$(id -u)" -eq 0 ]; then
	chown -R supybot:supybot /app
	exec su-exec supybot $0 "$@"
fi

if ! [ -z "$SUPYBOT_REPLACE_CONFIG" ] || ! [ -f run/supybot.conf ]; then
	python gen_config.py -o run/supybot.conf supybot.conf.in
fi

if [ ! -f run/conf/users.conf ]; then
	if [ -z "$SUPYBOT_OWNER_NAME" ]; then
		echo "ERROR: no users.conf and no SUPYBOT_OWNER_NAME" >&2
		exit 1
	fi

	if [ -z "$SUPYBOT_OWNER_PASSWORD" ]; then
		echo "ERROR: no users.conf and no SUPYBOT_OWNER_PASSWORD" >&2
		exit 1
	fi

	echo "generating supybot owner in run/conf/users.conf"

	mkdir -p run/conf
	supybot-adduser \
		-u "${SUPYBOT_OWNER_NAME}" \
		-p "${SUPYBOT_OWNER_PASSWORD}" \
		-c owner \
		run/conf/users.conf
fi

exec "$@"
