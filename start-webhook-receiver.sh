#!/bin/sh

: ${GH_HOOK_PORT:=8080}
: ${GH_LOG_LEVEL:=info}

exec gunicorn \
	-b 0.0.0.0:${GH_HOOK_PORT} \
	--log-level ${GH_LOG_LEVEL} \
	--access-logfile /dev/stderr \
	github_hook_receiver:app
