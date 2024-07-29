FROM ubuntu:22.04 as builder
SHELL ["/bin/bash", "-c"]
# https://stackoverflow.com/questions/53835198/integrating-python-poetry-with-docker
ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  POETRY_VERSION=1.8.3 \
  DEBIAN_FRONTEND=noninteractive

# We are cloning the code base internally
# to get all the required pieces

RUN apt-get update && apt-get install -y curl git python3 python3-pip python3-venv nano make
RUN python3 -m pip install "poetry==$POETRY_VERSION"
RUN poetry self add "poetry-dynamic-versioning[plugin]"
WORKDIR /code
COPY pyproject.toml poetry.lock Makefile .env ./
RUN set -a
RUN source .env
RUN set +a
COPY . .
EXPOSE 8081 8080
RUN poetry install

# CMD runs by default when no other commands are passed
# to a docker run directive from the command line.
CMD make start
