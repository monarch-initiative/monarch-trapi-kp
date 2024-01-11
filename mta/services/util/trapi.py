"""
TRAPI JSON accessing data utilities.
This module knows about the TRAPI syntax such that it can
extract parameters and build TRAPI Responses from results
"""
from typing import Optional, List, Dict
from functools import lru_cache
from mta.services.util import (
    TERM_DATA,
    MATCH_LIST,
    RESULTS_MAP,
    RESULT
)
from bmt import Toolkit


def extract_query_identifiers(trapi_json: Dict) -> Optional[List[str]]:
    """
    Interprets the TRAPI JSON content to figure out what specific
    parameters are needed for the execution of the Monarch query.
    :param trapi_json: Dict, TRAPI Query JSON object
    :return: Optional[List[str]], List of query identifiers identified as a set.
    """
    assert "query_graph" in trapi_json
    assert "nodes" in trapi_json["query_graph"]
    nodes: Dict = trapi_json["query_graph"]["nodes"]
    for node_id, details in nodes.items():
        # Example message with query identifier set:
        #
        # "message": {
        #       "query_graph": {
        #           "nodes": {
        #             "n0": {
        #               "categories": [
        #                 "biolink:PhenotypicFeature"
        #               ],
        #               "ids": [
        #                 "HP:0002104",
        #                 "HP:0012378",
        #                 "HP:0012378",
        #                 "HP:0012378"
        #               ],
        #               "is_set": true
        #             }
        # ...
        if not("ids" in details):
            continue

        # We generalize the capture of multi-CURIEs here.
        # This has the same outcome of the previous explicit
        # check for the required categories, but is more generic.
        if "is_set" in details and details["is_set"]:
            return list(details["ids"])

    return None


edge_idx = 0


def reset_edge_idx():
    global edge_idx
    edge_idx = 0


def next_edge_id() -> str:
    global edge_idx
    edge_idx += 1
    return f"e{str(edge_idx)}"


CATEGORY_MAP: Dict[str, List[str]] = {
    "biolink:PhenotypicFeature": [],
    "biolink:Disease": [],
}

_toolkit: Optional[Toolkit] = None


def get_toolkit() -> Toolkit:
    global _toolkit
    if not _toolkit:
        _toolkit = Toolkit()
    return _toolkit


@lru_cache()
def get_categories(category: str) -> List[str]:
    """
    Returns the full parent list of Biolink node categories for a most specific category.
    BMT can be used but for now, we hard code a look-up table?
    :param category: str, most specific category whose full categories list is to be retrieved
    :return: List[str], of the most specific category plus Biolink categories ancestral related to it
    """
    categories: List[str] = get_toolkit().get_ancestors(name=category, formatted=True, mixin=False)
    return categories


def build_trapi_message(result: RESULT) -> Dict:
    """
    Uses the object id indexed list of subjects to build the internal message contents of the knowledge graph.
    Input result is of format somewhat like
         { "MONDO:0008807": ["HP:0002104", "HP:0012378"] }
    which represent S-P-O edges something like
        ("HP:0002104": "biolink:PhenotypicFeature")--["biolink:similar_to"]->("MONDO:0008807": "biolink:Disease")

    First MVP assumes a fixed TRAPI Request QGraph structure.
    Future implementations may need to decide mappings more on the fly?

    :param result: RESULT, SemSimian subject - object identifier mapping dataset with some metadata annotation
    :return: query result parts of TRAPI Response.Message body (suitable KnowledgeGraph and Results added)
    """
    # Statement results as noted above, from original QGraph assumed to be of form:
    #
    # "query_graph": {
    #           "nodes": {
    #             "n0": {
    #               "categories": [
    #                 "biolink:PhenotypicFeature"
    #               ],
    #               "ids": [
    #                 "HP:0002104",
    #                 "HP:0012378"
    #               ],
    #               "is_set": true
    #             },
    #             "n1": {
    #               "categories": [
    #                 "biolink:Disease"
    #               ]
    #             }
    #           },
    #           "edges": {
    #             "e01": {
    #               "subject": "n0",
    #               "object": "n1",
    #               "predicates": [
    #                 "biolink:similar_to"
    #               ]
    #             }
    #           }
    #       }
    #
    # Add the following output parts:
    #
    #     "knowledge_graph": {
    #         "nodes": {
    #             "HP:0002104": {"categories": ["biolink:PhenotypicFeature"]},
    #             "HP:0012378": {"categories": ["biolink:PhenotypicFeature"]},
    #             "MONDO:0005148": {"categories": ["biolink:Disease"]}
    #         },
    #         "edges": {
    #             "e01": {
    #                 "subject": "HP:000210",
    #                 "object": "MONDO:0005148",
    #                 "predicate": "biolink:similar_to",
    #                 "attributes": [],
    #                 "sources":[
    #                     {
    #                         "resource_id": "infores:hpo-annotations",
    #                         "resource_role": "primary_knowledge_source"
    #                     }
    #                 ]
    #             },
    #             "e02": {
    #                 "subject": "HP:0012378",
    #                 "object": "MONDO:0005148",
    #                 "predicate": "biolink:similar_to",
    #                 "attributes": [],
    #                 "sources":[
    #                     {
    #                         "resource_id": "infores:hpo-annotations",
    #                         "resource_role": "primary_knowledge_source"
    #                     }
    #                 ]
    #             }
    #         }
    #     },
    #     "results": [
    #         {
    #             "node_bindings": {
    #                 "n0": [
    #                     {
    #
    #                         TODO: problem here is that the 'QNode'
    #                               n0 is a set of nodes?
    #                               How do we best represent this?
    #
    #                         "id": "HP:000210,HP:0012378"
    #                     }
    #                 ],
    #                 "n1": [
    #                     {
    #                         "id": "MONDO:0005148"
    #                     }
    #                 ]
    #             },
    #             "analyses": [
    #                 {
    #                     "resource_id": "infores:monarchinitiative",
    #                     "edge_bindings": {
    #                         "e01": [
    #                             {
    #                                 "id": "e01"
    #                             },
    #                             {
    #                                 "id": "e02"
    #                             },
    #                         ],
    #                     }
    #                 }
    #             ]
    #         }
    #     ]
    # }
    trapi_response: Dict = {
        "knowledge_graph": {
            "nodes": {},
            "edges": {}
        },
        "auxiliary_graphs": {},
        "results": []
    }
    primary_knowledge_source: str = result["primary_knowledge_source"]
    subject_id: str
    result_map: RESULTS_MAP = result["result_map"]
    reset_edge_idx()
    for subject_id, result in result_map.items():

        # 1. Add the "nodes" to the "knowledge_graph" - if not already present
        if subject_id not in trapi_response["knowledge_graph"]["nodes"]:
            subject_name = result["name"]
            subject_category = result["category"]
            trapi_response["knowledge_graph"]["nodes"][subject_id] = {
                "name": subject_name,
                "categories": get_categories(category=subject_category)
            }

        # 2. Need to create the overall "results" list entry
        #    for this similarity match, so that it can be
        #    populated concurrently with the knowledge_graph edges
        matched_terms: MATCH_LIST = result["matches"]
        term_data: TERM_DATA
        result_entry: Dict = {
            "node_bindings": {
                "n0": [
                    {

                        "id": ",".join([term_data["id"] for term_data in matched_terms])
                    }
                ],
                "n1": [
                    {
                        "id": subject_id
                    }
                ]
            },
            "analyses": [
                {
                    "resource_id": "infores:monarchinitiative",
                    "edge_bindings": {
                        "e01": []
                    }
                }
            ]
        }
        for term_data in matched_terms:
            if term_data["id"] not in trapi_response["knowledge_graph"]["nodes"]:
                trapi_response["knowledge_graph"]["nodes"][term_data["id"]] = {
                    "name": term_data["name"],
                    "categories": get_categories(category=term_data["category"])
                }

            # 3. Add the "edges" to the "knowledge_graph"...
            #         "edges": {
            #             "e01": {
            #                 "subject": "HP:000210",
            #                 "object": "MONDO:0005148",
            #                 "predicate": "biolink:similar_to",
            #                 "attributes": [],
            #                 "sources": [
            #                     {
            #                         "resource_id": "infores:hpo-annotations",
            #                         "resource_role": "primary_knowledge_source"
            #                     }
            #                 ]
            #             }
            edge_id = next_edge_id()
            # Note here that n0 are the subject but come from the SemSimian object terms
            trapi_response["knowledge_graph"]["edges"][edge_id] = {
                "subject": term_data["id"],
                "predicate": "biolink:similar_to",
                "object": subject_id,
                "attributes": [],
                "sources": [
                    {
                        "resource_id": primary_knowledge_source,
                        "resource_role": "primary_knowledge_source"
                    }
                ]
            }

            # 4. TODO: Capture the contents of the "auxiliary_graph" here?
            #
            #     "auxiliary_graphs": {
            #         "a0": {
            #             "edges": [
            #                 "e02",
            #                 "e12"
            #             ]
            #         },
            #         "a1": {
            #             "edges": [
            #                 "extra_edge0"
            #             ]
            #         },
            #         "a2": {
            #             "edges" [
            #                 "extra_edge1"
            #             ]
            #         }
            #     },

            # 5. ...then track the new edge as a specific "result" entry for the QEdge
            result_entry["analyses"][0]["edge_bindings"]["e01"].append({"id": edge_id})

        trapi_response["results"].append(result_entry)

    return trapi_response
