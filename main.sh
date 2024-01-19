#!/usr/bin/env bash

# set environment variables from .env
set -a
source .env
set +a

if [ "$MODE" == "deploy" ]; then
    echo "Deploying to gunicorn ${WEB_HOST}:${WEB_PORT}"
    gunicorn mtkp.services.server:APP -b ${WEB_HOST}:${WEB_PORT} -w 4 -k uvicorn.workers.UvicornWorker
else
    echo "Running uvicorn APP with --host ${WEB_HOST} --port ${WEB_PORT}"
    uvicorn mtkp.services.server:APP --host ${WEB_HOST} --port ${WEB_PORT} --reload
fi
