# Monarch Translator ARA

NCATS Translator ARA TRAPI wrapper for the Monarch Initiative system, specifically targeting TRAPI Multi-Curie Queries.

The initial implementation will support the following query: _**Given a set of (Human Phenotype Ontology term 'HP' term identified) phenotypes, what diseases might they match?**_

The goal is to find a good, probably creative answer that satisfies as many of the N inputs as possible, but may not satisfy all of them.

## Installation

## Running the Web Server Directly (from a Command Line Interface)

#### Install dependencies within a suitable virtual environment

The Python virtual environment and dependencies of MTA are managed using Poetry. Assuming that you have Poetry installed and a suitable version of Python (i.e. ">=3.9,<3.13") installed, then:

    poetry shell
    poetry install
 
#### Configure MTA settings
   
   Copy the `.env-template` file, saved as `.env` in repository root dir, then customize accordingly, for example:
   
   ```bash   
    WEB_HOST=0.0.0.0
    WEB_PORT=8080
    MTA_SERVICE_ADDRESS=localhost
    MTA_TITLE=MonarchTranslatorARA
    MTA_VERSION='1.4.0'
    BL_VERSION='4.1.0'
   ```

#### Run the Script

Run the following script to start up the server:

  ```bash
      ./main.sh
  ```

## Running the Server within a Docker Container

   Or build an image and run it. 
  
  ```bash
    cd mta
    docker build --tag <image_tag> .
    cd ../
  ```
  
  ```bash
   docker run --env-file .env\
    --name mta\
    -p 8080:8080\
    mta-tst

  ```

 ### Miscellaneous
 ###### `/about` Endpoint 
 The `/about` endpoint can be used to present meta-data about the current MTA instance. 
 This meta-data is served from `<repo-root>/mta/metadata/about.json` file. One can edit the contents of
 this file to suite needs. In containerized environment we recommend mounting this file as a volume.
 
 Eg:
 ```bash
docker run -p 0.0.0.0:8999:8080  \
               --env WEB_HOST=0.0.0.0 \
               -v <your-custom-about>:/<path-to-mta-repo-home>/mta/metadata/about.json \
               --network=<docker_network_neo4j_is_running_at> \    
                <image_tag>
    
``` 
