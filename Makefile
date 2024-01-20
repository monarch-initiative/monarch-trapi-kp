MAKEFLAGS += --warn-undefined-variables
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

start:
	poetry run gunicorn mtkp.services.server:APP --workers 4 --timeout 120 --worker-class uvicorn.workers.UvicornWorker --bind 54.87.193.222:8080 --log-level info --access-logfile combined_access_error.log --error-logfile combined_access_error.log --capture-output

start-dev:
	poetry run gunicorn mtkp.services.server:APP --workers 4 --timeout 120 --worker-class uvicorn.workers.UvicornWorker --bind 54.87.193.222:8081 --log-level info --access-logfile combined_access_error.log --error-logfile combined_access_error.log --capture-output
