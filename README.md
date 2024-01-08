# Monarch Translator ARA

NCATS Translator ARA TRAPI wrapper for the Monarch Initiative system, specifically targeting TRAPI Multi-Curie Queries.

The initial implementation will support the following query: _**Given a set of (Human Phenotype Ontology term 'HP' term identified) phenotypes, what diseases might they match?**_

The goal is to find a good, probably creative answer that satisfies as many of the N inputs as possible, but may not satisfy all of them.

## Installation

### Install dependencies within a suitable virtual environment

The Python virtual environment and dependencies of MTA are managed using Poetry. Assuming that you have Poetry installed and a suitable version of Python (i.e. ">=3.9,<3.13") installed, then:

    poetry shell
    poetry install
 
### Configure MTA settings
   
   Copy the `.env-template` file, saved as `.env` in repository root dir, then customize accordingly, for example:
   
   ```bash   
    WEB_HOST=0.0.0.0
    WEB_PORT=8080
    MTA_SERVICE_ADDRESS=localhost
    MTA_TITLE=MonarchTranslatorARA
    MTA_VERSION='1.4.0'
    BL_VERSION='4.1.0'
   ```

## Running the System

### Run the Server from the CLI

Run the following script to start up the server from the command line terminal:

  ```bash
      ./main.sh
  ```

### Running the Server within a Docker Container

   Or build an image and run it. From the root directory, type:
  
  ```bash
    docker build --tag mta-test .
    cd ../
  ```
  
  ```bash
   docker run --env-file .env\
    --name mta\
    -p 8080:8080\
    mta-test

  ```
## Viewing the System

When run the system locally from the CLI or using Docker (but not within any named host), an OpenAPI web form exposing the TRAPI API is available at http://localhost:8080/1.4/docs.  Of course, TRAPI endpoints may also be directly accessed, as expected.

An additional set of endpoints - so-called 'COMMON' API endpoints - is available at http://localhost:8080/common/docs.  Aside from accessing available release metadata about the system (via the /common/metadata path), this set of endpoints also provides a few non-TRAPI general purpose endpoints to retrieve specific data results more conveniently than TRAPI, such as retrieving a node record by CURIE.
