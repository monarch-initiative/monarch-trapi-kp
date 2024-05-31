"""
FastAPI app wrapper of generic methods.
"""
# import json
from typing import Any, List
from starlette.responses import Response
from fastapi import (
    # Body,
    Depends,
    FastAPI
)
# from fastapi.responses import JSONResponse
#
# from mmcq.models.models_trapi_1_5 import (
#     Message,
#     ReasonerRequest,
#     # CypherRequest,
#     SimpleSpecResponse,
#     SimpleSpecElement,
#     GraphSummaryResponse,
#     # CypherResponse,
#     PredicatesResponse
# )
# from mmcq.services.util.bl_helper import BLHelper
from mmcq.services.util.monarch_adapter import MonarchInterface
from mmcq.services.util.metadata import GraphMetadata
# from mmcq.services.util.overlay import Overlay
# from mmcq.services.util.question import Question
from mmcq.services.util.api_utils import (
    get_monarch_interface,
    # get_bl_helper,
    construct_open_api_schema,
    # get_example,
    get_graph_metadata,
    json_response
)


APP_COMMON = FastAPI(openapi_url='/common/openapi.json', docs_url='/common/docs')


#
# TODO: excluding this overlay() code in a first iteration of the Monarch TRAPI KP
#
# async def overlay(
#         request: ReasonerRequest = Body(
#             ...,
#             example={"message": get_example("overlay")},
#         ),
#         graph_interface: GraphInterface = Depends(get_monarch_interface),
# ) -> Message:
#     """Handle TRAPI request."""
#     overlay_class = Overlay(graph_interface)
#     return await overlay_class.overlay_support_edges(request.dict()["message"])
#
#
# APP_COMMON.add_api_route(
#     "/overlay",
#     overlay,
#     methods=["POST"],
#     response_model=Message,
#     description=(
#         "Given a ReasonerAPI graph, add support edges "
#         "for any nodes linked in result bindings."
#     ),
#     summary="Overlay results with available connections between each node.",
#     tags=["translator"]
# )


async def metadata(
        graph_metadata: GraphMetadata = Depends(get_graph_metadata),
) -> Response:
    """Handle /metadata."""
    result = await graph_metadata.get_metadata()
    return json_response(result)


APP_COMMON.add_api_route(
    path="/metadata",
    endpoint=metadata,
    methods=["GET"],
    response_model=Any,
    summary="Metadata about the knowledge graph.",
    description="Returns JSON with metadata about the data sources in this knowledge graph.",
)


async def one_hop(
        source_type: str,
        target_type: str,
        curie: str,
        monarch_interface: MonarchInterface = Depends(get_monarch_interface),
) -> Response:
    """Handle one-hop."""
    result = await monarch_interface.get_single_hops(source_type, target_type, curie)
    return json_response(result)


APP_COMMON.add_api_route(
    path="/{source_type}/{target_type}/{curie}",
    endpoint=one_hop,
    methods=["GET"],
    response_model=List,
    summary=(
        "Get one hop results from source type to target type. "
        "Note: Please GET /1.5/meta_knowledge_graph to determine "
        "what target goes with a source"
    ),
    description=(
        "Returns one hop paths from `source_node_type` "
        "with `curie` to `target_node_type`."
    ),
)


async def node(
        node_type: str,
        curie: str,
        monarch_interface: MonarchInterface = Depends(get_monarch_interface)
) -> Response:
    """Handle node lookup."""
    result = await monarch_interface.get_node(node_type, curie)
    return json_response(result)


APP_COMMON.add_api_route(
    path="/{node_type}/{curie}",
    endpoint=node,
    methods=["GET"],
    response_model=List,
    summary="Find `node` by `curie`",
    description="Returns `node` matching `curie`.",
)


#
# TODO: excluding this simple_spec() code in a first iteration of the Monarch TRAPI KP
#
# async def simple_spec(
#         source: str = None,
#         target: str = None,
#         monarch_interface: MonarchInterface = Depends(get_monarch_interface),
#         bl_helper: BLHelper = Depends(get_bl_helper),
# ) -> Response:
#     """Handle simple spec."""
#     source_id = source
#     target_id = target
#     if source_id or target_id:
#         minischema = []
#         mini_schema_raw = await graph_interface.get_mini_schema(
#             source_id,
#             target_id,
#         )
#         for row in mini_schema_raw:
#             source_labels = await bl_helper.get_most_specific_concept(
#                 row['source_label']
#             )
#             target_labels = await bl_helper.get_most_specific_concept(
#                 row['target_label']
#             )
#             for source_type in source_labels:
#                 for target_type in target_labels:
#                     minischema.append((
#                         source_type,
#                         row['predicate'],
#                         target_type,
#                     ))
#         minischema = list(set(minischema))  # remove dups
#         return list(map(lambda x: SimpleSpecElement(**{
#                 'source_type': x[0],
#                 'target_type': x[2],
#                 'edge_type': x[1],
#             }), minischema))
#     else:
#         schema = graph_interface.get_schema()
#         reformatted_schema = []
#         for source_type in schema:
#             for target_type in schema[source_type]:
#                 for edge in schema[source_type][target_type]:
#                     reformatted_schema.append(SimpleSpecElement(**{
#                         'source_type': source_type,
#                         'target_type': target_type,
#                         'edge_type': edge
#                     }))
#         return reformatted_schema
#
#
# APP_COMMON.add_api_route(
#     path="/simple_spec",
#     endpoint=simple_spec,
#     methods=["GET"],
#     response_model=SimpleSpecResponse,
#     summary="Get one-hop connection schema",
#     description=(
#         "Returns a list of available predicates when choosing a single source "
#         "or target curie. Calling this endpoint with no query parameters will "
#         "return all possible hops for all types."
#     ),
# )

APP_COMMON.openapi_schema = construct_open_api_schema(app=APP_COMMON, trapi_version="N/A")
