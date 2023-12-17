# monarch-translator-ara

NCATS Translator ARA TRAPI wrapper for the Monarch Initiative system

## Installation

To run the web server directly:

#### Install dependencies within a suitable virtual environment

The Python virtual environment and dependencies of MTA are managed using Poetry. Assuming that you have Poetry installed and a suitable version of Python (i.e. ">=3.9,<3.13") installed, then:

    poetry shell
    poetry install
 
#### Configure MTA settings
   
   Populate `.env-template` file with settings and save as `.env` in repo root dir.
   
   ```bash   
    WEB_HOST=0.0.0.0
    WEB_PORT=8080
    MTA_TITLE='MTA'
    MTA_VERSION='1.4.0'
    BL_VERSION='4.1.0'

   ```

#### Run Script
  
    ./main.sh

 ### DOCKER 
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
