from typing import Optional, List, Dict
import time
import copy
import json

import reasoner_transpiler as reasoner
from reasoner_transpiler.cypher import get_query
from reasoner_pydantic.qgraph import AttributeConstraint
from reasoner_pydantic.shared import Attribute

from mta.services.config import config
from mta.services.util import RESULT
from mta.services.util.constraints import check_attributes
from mta.services.util.attribute_mapping import (
    map_data,
    skip_list,
    get_attribute_bl_info
)
from mta.services.util.logutil import LoggingUtil
from mta.services.util.trapi import (
    TargetQueryType,
    extract_trapi_parameters,
    build_trapi_message
)
from mta.services.util.monarch_adapter import MonarchInterface

# set the transpiler attribute mappings
reasoner.cypher.ATTRIBUTE_TYPES = map_data['attribute_type_map']

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

    def __init__(self, question_json):
        self._question_json = copy.deepcopy(question_json)

        # self.toolkit = toolkit
        self.provenance = config.get("PROVENANCE_TAG", "infores:monarchinitiative")

    def _construct_sources_tree(self, sources):
        # if primary source and aggregator source are specified in the graph,
        # upstream_resource_ids of all aggregator_ks be that source

        # if aggregator ks are coming from db, mta would add itself as aggregator and use other aggregator ids
        # as upstream resources, if no aggregators are found and only primary ks is provided that would be added
        # as upstream for the mta entry
        formatted_sources = []
        # filter out source entries that actually have values
        temp = {}
        for source in sources:
            if not source['resource_id']:
                continue
            temp[source['resource_role']] = temp.get(source['resource_role'], set())
            if isinstance(source["resource_id"], str):
                temp[source["resource_role"]].add(source["resource_id"])
            elif isinstance(source["resource_id"], list):
                for resource_id in source["resource_id"]:
                    temp[source["resource_role"]].add(resource_id)

        for resource_role in temp:
            upstreams = None
            if resource_role == "aggregator_knowledge_source":
                upstreams = temp.get("primary_knowledge_source", None)

            formatted_sources += [
                {
                    "resource_id": resource_id,
                    "resource_role": resource_role,
                    "upstream_resource_ids": list(upstreams) if upstreams else None
                }
                for resource_id in temp[resource_role]
            ]
        upstreams_for_mta_entry = \
            temp.get("aggregator_knowledge_source") or temp.get("primary_knowledge_source")
        formatted_sources.append({
            "resource_id": self.provenance,
            "resource_role": "aggregator_knowledge_source",
            "upstream_resource_ids": list(upstreams_for_mta_entry) if upstreams_for_mta_entry else None
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
                qualifier_results = [attrib for attrib in attributes
                                     if 'qualifie' in attrib['original_attribute_name']]
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
            new_attribs = [attrib for attrib in attributes
                           if attrib['original_attribute_name'] not in props and
                           attrib['original_attribute_name'] not in skip_list and
                           'qualifie' not in attrib['original_attribute_name']
                           ]

            # for the non-core properties
            for attr in new_attribs:
                # make sure the original_attribute_name has something other than none
                attr['original_attribute_name'] = attr['original_attribute_name'] or ''

                # map the attribute type to the list above, otherwise generic default
                attr["value_type_id"] = VALUE_TYPES.get(attr["original_attribute_name"], "EDAM:data_0006")

                # uses generic data as attribute type id if not defined
                if not ("attribute_type_id" in attr and attr["attribute_type_id"] != 'NA'):
                    attribute_data = get_attribute_bl_info(attr["original_attribute_name"])
                    if attribute_data:
                        attr.update(attribute_data)

            # update edge provenance with automat infores, filter empty ones, expand list type resource ids
            if not node:
                kg_items[identifier]["sources"] = self._construct_sources_tree(kg_items[identifier].get("sources", []))
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
        logger.info(f"answering query_graph: {json.dumps(self._question_json)}")
        parameters: Optional[List[str]] = extract_trapi_parameters(
            trapi_json=self._question_json,
            # TODO: the 'target_query_input' argument feels hacky -
            #       'answer' should be more agnostic about the query.
            target_query_input=TargetQueryType.HP_IDS
        )
        trapi_message: Dict = dict()
        if parameters:
            results: Dict[str, List[str]]
            start = time.time()
            result: RESULT = await monarch_interface.run_query(parameters)
            end = time.time()
            logger.info(f"getting answers took {end - start} seconds")

            trapi_message = build_trapi_message(result=result)

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
