FROM python:3.9

# We are cloning the code base internally
# to get all the required pieces
WORKDIR /code
RUN git clone --single-branch https://github.com/monarch-initiative/monarch-translator-ara.git
WORKDIR /code/monarch-translator-ara
ENV PYTHONPATH=/code/monarch-translator-ara

# All environment files customized locally
# by the creator of the Docker container
COPY *.env .

# Installing the poetry dependencies
# no need for a virtual shell though...
RUN pip install poetry
RUN poetry config virtualenvs.create false
RUN poetry install -n --no-ansi

# Run the beast!
EXPOSE 8080
RUN mkdir -p ./mta/logs
ENTRYPOINT ["./main.sh"]
