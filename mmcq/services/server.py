"""FastAPI app."""
import logging
import warnings
import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from mmcq.services.config import config
from mmcq.services.util.logutil import LoggingUtil
from mmcq.services.app_common import APP_COMMON
from mmcq.services.app_trapi_1_5 import APP_TRAPI_1_5
from mmcq.services.util.api_utils import construct_open_api_schema

TITLE = config.get('MMCQ_TITLE', 'Monarch TRAPI KP')

VERSION = os.environ.get('MMCQ_VERSION', '1.5.0')

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

APP = FastAPI()

# CORS
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount 1.5 app at /1.5
APP.mount('/1.5', APP_TRAPI_1_5, 'Trapi 1.5')

# Mount non-TRAPI supplemental API endpoints at /
APP.mount('/', APP_COMMON, '')

# Add all routes of each app for open api generation at /openapi.json
# This will create an aggregate openapi spec.
APP.include_router(APP_TRAPI_1_5.router, prefix='/1.5')
APP.include_router(APP_COMMON.router)

# Construct app /openapi.json... Note that this schema
# will not be registered on the Translator SmartAPI registry.
# Instead, /1.5/openapi.json should be SmartAPI registered.
APP.openapi_schema = construct_open_api_schema(app=APP, trapi_version='N/A')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("mmcq.services.server:APP", host="0.0.0.0", port=8080, log_level="info", reload=True)
