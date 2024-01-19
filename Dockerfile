FROM ubuntu:22.04 as builder

# https://stackoverflow.com/questions/53835198/integrating-python-poetry-with-docker
ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  # TODO: check if this is still needed, or can use 1.2
  POETRY_VERSION=1.3.2 \
  DEBIAN_FRONTEND=noninteractive

# We are cloning the code base internally
# to get all the required pieces

RUN apt-get update && apt-get install -y curl git python3-pip python3 nano make
RUN python3 -m pip install "poetry==$POETRY_VERSION"
RUN poetry self add "poetry-dynamic-versioning[plugin]"
WORKDIR /code
COPY pyproject.toml poetry.lock README.md Makefile .
COPY . .

RUN git clone --single-branch https://github.com/monarch-initiative/monarch-trapi-kp.git
WORKDIR /code/monarch-trapi-kp
ENV PYTHONPATH=/code/monarch-trapi-kp

RUN rm -rf .venv
EXPOSE 8081 8080
RUN poetry install

# CMD runs by default when no other commands are passed to a docker run directive from the command line.

CMD make start
