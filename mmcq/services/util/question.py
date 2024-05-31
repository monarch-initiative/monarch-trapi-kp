from typing import List, Dict, Optional
import time
import copy
import json

from reasoner_pydantic.qgraph import AttributeConstraint
from reasoner_pydantic.shared import Attribute

from mmcq.services.config import config
from mmcq.services.util import DEFAULT_PROVENANCE, RESULT
from mmcq.services.util.constraints import check_attributes
from mmcq.services.util.attribute_mapping import (
    map_data,
    skip_list,
    get_attribute_bl_info
)
from mmcq.services.util.logutil import LoggingUtil
from mmcq.services.util.trapi import build_trapi_message
from mmcq.services.util.monarch_adapter import MonarchInterface

# set the value type mappings
VALUE_TYPES = map_data['value_type_map']

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format')
)


class Question:
    # SPEC VARS
    QUERY_GRAPH_KEY = 'query_graph'
    KG_ID_KEY = 'ids'
    QG_ID_KEY = 'ids'
    ANSWERS_KEY = 'results'
    KNOWLEDGE_GRAPH_KEY = 'knowledge_graph'
    NODES_LIST_KEY = 'nodes'
    EDGES_LIST_KEY = 'edges'
    NODE_TYPE_KEY = 'categories'
    EDGE_TYPE_KEY = 'predicate'
    SOURCE_KEY = 'subject'
    TARGET_KEY = 'object'
    NODE_BINDINGS_KEY = 'node_bindings'
    EDGE_BINDINGS_KEY = 'edge_bindings'
    CURIE_KEY = 'curie'

    def __init__(self, question_json, result_limit: int):
        """
        Constructor for a Question.
        :param question_json: the contents of a TRAPI Query.Message JSON blob
        :param result_limit: a non-TRAPI extra property indicating
                             the limit on query results to be returned.
        """
        # Example Query Graph for the Monarch SemSimian KP
        # {
        #   "message": {
        #     "query_graph": {
        #       "nodes": {
        #         "n0": {
        #           "ids": [
        #             "HP:0002104",
        #             "HP:0012378"
        #           ],
        #           "categories": [
        #             "biolink:PhenotypicFeature"
        #           ],
        #           "is_set": true,
        #           "constraints": [],
        #           "set_interpretation": "MANY"
        #         },
        #         "n1": {
        #           "ids": null,
        #           "categories": [
        #             "biolink:Disease"
        #           ],
        #           "is_set": false,
        #           "constraints": []
        #         }
        #       },
        #       "edges": {
        #         "e01": {
        #           "subject": "n0",
        #           "object": "n1",
        #           "knowledge_type": null,
        #           "predicates": [
        #             "biolink:similar_to"
        #           ],
        #           "attribute_constraints": [],
        #           "qualifier_constraints": []
        #         }
        #       }
        #     }
        self._question_json = copy.deepcopy(question_json)
        self._result_limit = result_limit

        # self.toolkit = toolkit
        self.provenance = config.get("PROVENANCE_TAG", DEFAULT_PROVENANCE)

    def _construct_sources_tree(self, sources: List[Dict]) -> List[Dict]:
        """
        Method to fill out the full annotation for edge "sources"
        entries including "upstream_resource_ids" tree.
        :param sources: List[Dict], edge 'sources' property entries
        :return: enhanced "sources" including top-level "Monarch TRAPI" source entry.
        """
        if not sources:
            # empty sources.. pretty strange, but then just send back
            # an instance of the top-level "Monarch TRAPI" source entry
            return [
                {
                    "resource_id": self.provenance,
                    "resource_role": "aggregator_knowledge_source",
                    "source_record_urls": None,
                    "upstream_resource_ids":  None
                }
            ]

        # if primary source and aggregator source are specified in the graph,
        # upstream_resource_ids of all aggregator_ks be that source

        # if aggregator ks are coming from db, mmcq would add itself as aggregator and use other aggregator ids
        # as upstream resources, if no aggregators are found and only primary ks is provided that would be added
        # as upstream for the mmcq entry
        formatted_sources = []
        resource_ids_with_resource_role = dict()
        source_record_urls_to_resource_id = dict()

        # filter out source entries that actually have values
        for source in sources:

            if not (
                    'resource_id' in source and
                    source['resource_id'] and
                    'resource_role' in source and
                    source['resource_role']
            ):
                # silently pruning TRAPI non-compliant source records
                logger.warning(f"Invalid edge 'source' entry: '{str(source)}'? Skipped!")
                continue

            # 'resource_role' values are now ResourceRoleEnum without a biolink: CURIE prefix
            source['resource_role'] = source['resource_role'].lstrip("biolink:")

            resource_ids_with_resource_role[source['resource_role']] = \
                resource_ids_with_resource_role.setdefault(source['resource_role'], set())

            source_record_urls_to_resource_id[source['resource_id']] = \
                source['source_record_urls'] if 'source_record_urls' in source else None

            if isinstance(source["resource_id"], str):
                resource_ids_with_resource_role[source["resource_role"]].add(source["resource_id"])
            elif isinstance(source["resource_id"], list):
                for resource_id in source["resource_id"]:
                    resource_ids_with_resource_role[source["resource_role"]].add(resource_id)

        for resource_role in resource_ids_with_resource_role:

            upstreams: Optional[Dict] = None

            if resource_role == "aggregator_knowledge_source":
                upstreams = resource_ids_with_resource_role.get("primary_knowledge_source", None)
            elif resource_role == "primary_knowledge_source":
                upstreams = resource_ids_with_resource_role.get("supporting_data_source", None)

            formatted_sources += [
                {
                    "resource_id": resource_id,
                    "resource_role": resource_role,
                    "source_record_urls": source_record_urls_to_resource_id[resource_id],
                    "upstream_resource_ids": list(upstreams) if upstreams else None
                }
                for resource_id in resource_ids_with_resource_role[resource_role]
            ]

        upstreams_for_top_level_entry = \
            resource_ids_with_resource_role.get("aggregator_knowledge_source") or \
            resource_ids_with_resource_role.get("primary_knowledge_source") or \
            resource_ids_with_resource_role.get("supporting_data_source")

        formatted_sources.append({
            "resource_id": self.provenance,
            "resource_role": "aggregator_knowledge_source",
            "source_record_urls": None,
            "upstream_resource_ids": list(upstreams_for_top_level_entry) if upstreams_for_top_level_entry else None
        })

        return formatted_sources

    def format_attribute_trapi(self, kg_items, node=False):
        for identifier in kg_items:
            # get the properties for the record
            props = kg_items[identifier]

            # save the transpiler attribs
            attributes = props.get('attributes', [])

            # separate the qualifiers from attributes for edges and format them
            if not node:
                qualifier_results = [
                    attrib for attrib in attributes
                    if 'original_attribute_name' in attrib and 'qualifie' in attrib['original_attribute_name']
                ]
                if qualifier_results:
                    formatted_qualifiers = []
                    for qualifier in qualifier_results:
                        formatted_qualifiers.append({
                            "qualifier_type_id": f"biolink:{qualifier['original_attribute_name']}"
                            if not qualifier['original_attribute_name'].startswith("biolink:")
                            else qualifier['original_attribute_name'],
                            "qualifier_value": qualifier['value']
                        })
                    props['qualifiers'] = formatted_qualifiers

            # create a new list that doesn't have the core properties or qualifiers
            new_attribs: List = list()
            for attrib in attributes:
                if 'original_attribute_name' not in attrib or (
                        attrib['original_attribute_name'] not in props and
                        attrib['original_attribute_name'] not in skip_list and
                        'qualifie' not in attrib['original_attribute_name']
                ):
                    new_attribs.append(attrib)

            # for the non-core properties
            for attr in new_attribs:
                # make sure the original_attribute_name has something other than none
                attr['original_attribute_name'] = \
                    ('original_attribute_name' in attr and attr['original_attribute_name']) or ''

                # map the attribute type to the list above, otherwise generic default
                attr["value_type_id"] = \
                    ("value_type_id" in attr and attr["value_type_id"]) or \
                    VALUE_TYPES.get(attr["original_attribute_name"], "EDAM:data_0006")

                # uses generic data as attribute type id if not defined
                if not ("attribute_type_id" in attr and attr["attribute_type_id"] != 'NA'):
                    attribute_data = get_attribute_bl_info(attr["original_attribute_name"])
                    if attribute_data:
                        attr.update(attribute_data)

            # update edge provenance with infores,
            # filter empty ones, expand list type resource ids
            if not node:
                kg_items[identifier]["sources"] = \
                    self._construct_sources_tree(kg_items[identifier].get("sources", []))

            # assign these attribs back to the original attrib list without the core properties
            props['attributes'] = new_attribs

        return kg_items

    def transform_attributes(self, trapi_message):
        self.format_attribute_trapi(trapi_message.get('knowledge_graph', {}).get('nodes', {}), node=True)
        self.format_attribute_trapi(trapi_message.get('knowledge_graph', {}).get('edges', {}))
        for r in trapi_message.get("results", []):
            # add resource id
            for analyses in r["analyses"]:
                analyses["resource_id"] = self.provenance
        return trapi_message

    async def answer(self, monarch_interface: MonarchInterface):
        """
        Gives a TRAPI response by updating the query graph
        with answers retrieved from the Monarch backend.
        :param monarch_interface: interface for Monarch
        :return: Dict, TRAPI JSON Response object
        """
        logger.info(f"TRAPI query answering query_graph: {json.dumps(self._question_json)}")

        results: Dict[str, List[str]]
        start = time.time()
        result: RESULT = await monarch_interface.run_query(
            trapi_message=self._question_json, result_limit=self._result_limit
        )
        end = time.time()
        logger.info(f"SemSimian query took {end - start} seconds")

        if "error" in result:
            return result

        trapi_message: Dict = build_trapi_message(trapi_message=self._question_json, result=result)

        # May be unaltered if parameters were unavailable
        self._question_json.update(self.transform_attributes(trapi_message))
        self._question_json = Question.apply_attribute_constraints(self._question_json)

        return self._question_json

    @staticmethod
    def apply_attribute_constraints(message):
        q_nodes = message['query_graph'].get('nodes', {})
        q_edges = message['query_graph'].get('edges', {})
        node_constraints = {
            q_id: [AttributeConstraint(**constraint) for constraint in q_nodes[q_id]['constraints']] for q_id in q_nodes
            if q_nodes[q_id]['constraints']
        }
        edge_constraints = {
            q_id: [AttributeConstraint(**constraint)
                   for constraint in q_edges[q_id]['attribute_constraints']] for q_id in q_edges
            if q_edges[q_id]['attribute_constraints']
        }
        # if there are no constraints no need to do stuff.
        if not(len(node_constraints) or len(edge_constraints)):
            return message
        # grab kg_ids for constrained items
        constrained_node_ids = {}
        constrained_edge_ids = {}
        for r in message['results']:
            for q_id in node_constraints.keys():
                for node in r['node_bindings'][q_id]:
                    constrained_node_ids[node['id']] = node_constraints[q_id]
            for q_id in edge_constraints.keys():
                for analyses in r['analyses']:
                    for edge in analyses.get('edge_bindings', {}).get(q_id, []):
                        constrained_edge_ids[edge['id']] = edge_constraints[q_id]
        # mark nodes for deletion
        nodes_to_filter = set()
        for node_id in constrained_node_ids:
            kg_node = message['knowledge_graph']['nodes'][node_id]
            attributes = [Attribute(**attr) for attr in kg_node['attributes']]
            keep = check_attributes(attribute_constraints=constrained_node_ids[node_id], db_attributes=attributes)
            if not keep:
                nodes_to_filter.add(node_id)
        # mark edges for deletion
        edges_to_filter = set()
        for edge_id, edge in message['knowledge_graph']['edges'].items():
            # if node is to be removed, remove its linking edges as well
            if edge['subject'] in nodes_to_filter or edge['object'] in nodes_to_filter:
                edges_to_filter.add(edge_id)
                continue
            # else check if edge is in constrained list and do filter
            if edge_id in constrained_edge_ids:
                attributes = [Attribute(**attr) for attr in edge['attributes']]
                keep = check_attributes(attribute_constraints=constrained_edge_ids[edge_id], db_attributes=attributes)
                if not keep:
                    edges_to_filter.add(edge_id)
        # remove some nodes
        filtered_kg_nodes = {node_id: node for node_id, node in message['knowledge_graph']['nodes'].items()
                             if node_id not in nodes_to_filter
                             }
        # remove some edges, also those linking to filtered nodes
        filtered_kg_edges = {edge_id: edge for edge_id, edge in message['knowledge_graph']['edges'].items()
                             if edge_id not in edges_to_filter
                             }
        # results binding fun!
        filtered_bindings = []
        for result in message['results']:
            skip_result = False
            new_node_bindings = {}
            for q_id, binding in result['node_bindings'].items():
                binding_new = [x for x in binding if x['id'] not in nodes_to_filter]
                # if this list is empty well, skip the whole result
                if not binding_new:
                    skip_result = True
                    break
                new_node_bindings[q_id] = binding_new
            # if node bindings are empty for a q_id skip the whole result
            if skip_result:
                continue
            for analysis in result["analyses"]:
                new_edge_bindings = {}
                for q_id, binding in analysis["edge_bindings"].items():
                    binding_new = [x for x in binding if x['id'] not in edges_to_filter]
                    # if this list is empty well, skip the whole result
                    if not binding_new:
                        skip_result = True
                        break
                    new_edge_bindings[q_id] = binding_new
                analysis["edge_bindings"] = new_edge_bindings
            # if edge bindings are empty for a q_id skip the whole result
            if skip_result:
                continue
            filtered_bindings.append({
                "node_bindings": new_node_bindings,
                "analyses": result["analyses"]
            })

        return {
            "query_graph": message['query_graph'],
            "knowledge_graph": {
                "nodes": filtered_kg_nodes,
                "edges": filtered_kg_edges
            },
            "results": filtered_bindings
        }

    @staticmethod
    def transform_schema_to_question_template(graph_schema):
        """
        Returns array of Templates given a graph schema
        Eg: if schema looks like
           {
            "Type 1" : {
                "Type 2": [
                    "edge 1"
                ]
            }
           }
           We would get
           {
            "question_graph": {
                "nodes" : {
                    "n1": {
                        "id": "{{ curie }}",
                        "category": "Type 1"
                    },
                    "n2": {
                        "id" : "{{ curie }}",
                        "category": "Type 2"
                    }
                },
                "edges":{
                    "e1": {
                        "predicate": "edge 1",
                        "subject": "n1",
                        "object": "n2"
                    }
                ]
            }
           }
        :param graph_schema:
        :return:
        """
        question_templates = []
        question_graph: Dict = dict()
        for source_type in graph_schema:
            target_set = graph_schema[source_type]
            for target_type in target_set:
                question_graph = {
                    Question.NODES_LIST_KEY: {
                        "n1": {
                            'id': None,
                            Question.NODE_TYPE_KEY: source_type,
                        },
                        "n2": {
                            'id': None,
                            Question.NODE_TYPE_KEY: target_type,
                        }
                    },
                    Question.EDGES_LIST_KEY: []
                }
                edge_set = target_set[target_type]
                question_graph[Question.EDGES_LIST_KEY] = {}
                for index, edge_type in enumerate(set(edge_set)):
                    edge_dict = {
                        Question.SOURCE_KEY: "n1",
                        Question.TARGET_KEY: "n2",
                        Question.EDGE_TYPE_KEY: edge_type
                    }
                    question_graph[Question.EDGES_LIST_KEY][f"e{index}"] = edge_dict
            question_templates.append({Question.QUERY_GRAPH_KEY: question_graph})
        return question_templates
