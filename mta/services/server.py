"""FastAPI app."""
import logging
import warnings
import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from mta.services.config import config
from mta.services.util.logutil import LoggingUtil
from mta.services.app_common import APP_COMMON
from mta.services.app_trapi_1_4 import APP_TRAPI_1_4
from mta.services.util.api_utils import construct_open_api_schema

TITLE = config.get('MTA_TITLE', 'Monarch Translator ARA')

VERSION = os.environ.get('MTA_VERSION', '1.4.0')

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

APP = FastAPI()

# Mount 1.4 app at /1.4
APP.mount('/1.4', APP_TRAPI_1_4, 'Trapi 1.4')

# Mount non-TRAPI supplemental API endpoints at /
APP.mount('/', APP_COMMON, '')

# Add all routes of each app for open api generation at /openapi.json
# This will create an aggregate openapi spec.
APP.include_router(APP_TRAPI_1_4.router, prefix='/1.4')
APP.include_router(APP_COMMON.router)

# Construct app /openapi.json... Note that this schema
# will not be registered on the Translator SmartAPI registry.
# Instead, /1.4/openapi.json should be SmartAPI registered.
APP.openapi_schema = construct_open_api_schema(app=APP, trapi_version='N/A')

# CORS
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.environ.get("OTEL_ENABLED"):
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry import trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.resources import SERVICE_NAME as TELEMETRY_SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # httpx connections need to be open a little longer by the otel decorators
    # but some libs display warnings of resource being unclosed.
    # This suppresses such warnings.
    logging.captureWarnings(capture=True)
    warnings.filterwarnings("ignore", category=ResourceWarning)
    service_name = os.environ.get('MTA_TITLE', 'MTA')

    assert service_name and isinstance(service_name, str)

    trace.set_tracer_provider(
        TracerProvider(
            resource=Resource.create({TELEMETRY_SERVICE_NAME: service_name})
        )
    )
    jaeger_exporter = JaegerExporter(
        agent_host_name=os.environ.get("JAEGER_HOST", "localhost"),
        agent_port=int(os.environ.get("JAEGER_PORT", "6831")),
    )

    # TODO: OpenTelemetry version discord: now missing this method...
    #       This needs to be fixed once we start using OpenTelemetry!
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
    tracer = trace.get_tracer(__name__)
    FastAPIInstrumentor.instrument_app(APP, tracer_provider=trace, excluded_urls="docs,openapi.json")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(APP, host='0.0.0.0', port=8080)
