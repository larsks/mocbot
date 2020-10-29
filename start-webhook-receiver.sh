#!/bin/sh

: ${GH_HOOK_PORT:=8080}

exec gunicorn -b 0.0.0.0:${GH_HOOK_PORT} github_hook_receiver:app
