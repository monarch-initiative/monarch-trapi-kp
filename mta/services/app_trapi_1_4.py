"""FastAPI app."""

from fastapi import Body, Depends, FastAPI, Response, status
from reasoner_transpiler.exceptions import InvalidPredicateError
from reasoner_pydantic import MetaKnowledgeGraph
from mta.models.models_trapi_1_4 import ReasonerRequest


from mta.services.util.monarch_adapter import MonarchInterface
from mta.services.util.metadata import GraphMetadata
from mta.services.util.question import Question
# from mta.services.util.overlay import Overlay
from mta.services.util.api_utils import (
    get_monarch_interface,
    get_graph_metadata,
    construct_open_api_schema,
    get_example,
    json_response
)

# Mount open api at /1.4/openapi.json
APP_TRAPI_1_4 = FastAPI(openapi_url="/openapi.json", docs_url="/docs", root_path='/1.4')


#
# TODO: SRI Testing data is deprecated?
#
# async def get_sri_testing_data(
#         graph_metadata: GraphMetadata = Depends(get_graph_metadata),
# ) -> SRITestData:
#     """Handle /sri_testing_data."""
#     sri_test_data = await graph_metadata.get_sri_testing_data()
#     return sri_test_data
#
# APP_TRAPI_1_4.add_api_route(
#     "/sri_testing_data",
#     get_sri_testing_data,
#     methods=["GET"],
#     response_model=SRITestData,
#     response_model_exclude_none=True,
#     summary="Test data for usage by the SRI Testing Harness.",
#     description="Returns a list of edges that are representative examples of the knowledge graph.",
#     tags=["trapi"]
# )


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


APP_TRAPI_1_4.add_api_route(
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
            example=get_example("reasoner-trapi-1.4"),
        ),
        monarch_interface: MonarchInterface = Depends(get_monarch_interface)
) -> Response:
    """
    Handle TRAPI request.
    :return: starlette Response wrapped ReasonerRequest.
    :rtype: Response(ReasonerRequest)
    """
    request_json = request.dict(by_alias=True)

    # default workflow
    workflow = request_json.get('workflow') or [{"id": "lookup"}]
    workflows = {wkfl['id']: wkfl for wkfl in workflow}
    if 'lookup' in workflows:
        question = Question(request_json["message"])
        try:
            response_message = await question.answer(monarch_interface)
            request_json.update({'message': response_message, 'workflow': workflow})
        except InvalidPredicateError as e:
            response.status_code = status.HTTP_400_BAD_REQUEST
            request_json["description"] = str(e)

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


APP_TRAPI_1_4.add_api_route(
    path="/query",
    endpoint=reasoner_api,
    methods=["POST"],
    response_model=ReasonerRequest,
    summary="Query reasoner via one of several inputs.",
    description="",
    tags=["trapi"]
)

APP_TRAPI_1_4.openapi_schema = construct_open_api_schema(app=APP_TRAPI_1_4, trapi_version="1.4.0", prefix='/1.4')
