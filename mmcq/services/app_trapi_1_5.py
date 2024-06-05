"""FastAPI app."""
from typing import Optional, Any
from fastapi import Body, Depends, FastAPI, Response, status
from reasoner_pydantic import MetaKnowledgeGraph
from mmcq.models.models_trapi_1_5 import ReasonerRequest

from mmcq.services.config import config
from mmcq.services.util.monarch_adapter import MonarchInterface
from mmcq.services.util.metadata import GraphMetadata
from mmcq.services.util.question import Question
# from mmcq.services.util.overlay import Overlay
from mmcq.services.util.api_utils import (
    get_monarch_interface,
    get_graph_metadata,
    construct_open_api_schema,
    get_example,
    json_response
)
from mmcq.services.util.logutil import LoggingUtil

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format')
)

# Mount open api at /1.5/openapi.json
APP_TRAPI_1_5 = FastAPI(openapi_url="/openapi.json", docs_url="/docs", root_path='/1.5')


async def get_meta_knowledge_graph(
        graph_metadata: GraphMetadata = Depends(get_graph_metadata),
) -> Response:
    """
    Handle /meta_knowledge_graph.
    :return: starlette Response wrapped MetaKnowledgeGraph.
    :rtype: Response(MetaKnowledgeGraph)
    """
    meta_kg = await graph_metadata.get_meta_kg()
    return json_response(meta_kg)


APP_TRAPI_1_5.add_api_route(
    path="/meta_knowledge_graph",
    endpoint=get_meta_knowledge_graph,
    methods=["GET"],
    response_model=MetaKnowledgeGraph,
    summary="Meta knowledge graph representation of this TRAPI web service.",
    description="Returns meta knowledge graph representation of this TRAPI web service.",
    tags=["trapi"]
)


async def reasoner_api(
        response: Response,
        request: ReasonerRequest = Body(
            ...,
            # Works for now but in deployment would be
            # replaced by a mount, specific to backend dataset
            example=get_example("reasoner-trapi-1.5"),
        ),
        monarch_interface: MonarchInterface = Depends(get_monarch_interface)
) -> Response:
    """
    Handle TRAPI Query request.
    :return: starlette wrapped ReasonerRequest.
    :rtype: Response(ReasonerRequest)
    """
    request_json = request.dict(by_alias=True)

    # This is an application-specific
    # TRAPI Query OpenAPI "additionalProperties" value
    result_limit: int
    limit: Optional = None
    try:
        limit: Optional[Any] = request_json.get('limit')
        result_limit = int(limit) if limit is not None else 10
    except (ValueError, TypeError):
        logger.warning(f"Invalid result limit string {limit} in TRAPI Query JSON. Setting to default 10 value.")
        result_limit = 10

    # default workflow
    workflow = request_json.get('workflow') or [{"id": "lookup", "parameters": None, "runner_parameters": None}]
    workflows = {wkfl['id']: wkfl for wkfl in workflow}

    # TODO: do we need a new 'workflow' code to explicitly signal the 'multi-curie' use case?
    if 'lookup' in workflows:
        question = Question(request_json["message"], result_limit=result_limit)
        try:
            response_message = await question.answer(monarch_interface)
            request_json.update({'message': response_message, 'workflow': workflow})
        except RuntimeError as rte:
            response.status_code = status.HTTP_400_BAD_REQUEST
            request_json["description"] = str(rte)

    #
    # TODO: don't have overlays in this first iteration?
    #
    # elif 'overlay_connect_knodes' in workflows:
    #     overlay = Overlay(graph_interface=graph_interface)
    #     response_message = await overlay.connect_k_nodes(request_json['message'])
    #     request_json.update({'message': response_message, 'workflow': workflow})
    #
    # elif 'annotate_nodes' in workflows:
    #     overlay = Overlay(graph_interface=graph_interface)
    #     response_message = await overlay.annotate_node(request_json['message'])
    #     request_json.update({'message': response_message, 'workflow': workflow})

    return json_response(request_json)


APP_TRAPI_1_5.add_api_route(
    path="/query",
    endpoint=reasoner_api,
    methods=["POST"],
    response_model=ReasonerRequest,
    summary="Query reasoner via one of several inputs.",
    description="",
    tags=["trapi"]
)

APP_TRAPI_1_5.openapi_schema = construct_open_api_schema(app=APP_TRAPI_1_5, trapi_version="1.5.0", prefix='/1.5')
