#!/bin/sh

if [ "$(id -u)" -eq 0 ]; then
	chown -R mocbot:mocbot /app
	exec su-exec mocbot $0 "$@"
fi

if [ "$1" = "sh" ]; then
	exec /bin/sh
fi

exec "$@"
