"""
TRAPI JSON accessing data utilities.
This module knows about the TRAPI syntax such that it can
extract parameters and build TRAPI Responses from results
"""
from typing import Optional, List, Dict, Set
from functools import lru_cache
from copy import deepcopy
from uuid import uuid4
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
    Input result is a RESULT dictionary of format somewhat like:
    {
        "primary_knowledge_source": "infores:semsimian-kp",
        "ingest_knowledge_source": "infores:hpo-annotations",
        "result_map": {
            "MONDO:0008807": {
                "name": "obsolete apnea, central sleep",
                "category": "biolink:Disease",
                "supporting_data_sources": ["infores:hpo-annotations", "infores:upheno"],
                "score": 13.074943444390097,
                "matches": [
                    {
                        "id": "HP:0002104",
                        "name": "Fatigue (HPO)",
                        "category": "biolink:PhenotypicFeature"
                    },
                    {
                        "id": "HP:0012378",
                        "name": "Apnea (HPO)",
                        "category": "biolink:PhenotypicFeature"
                    }
                ]
            },
            ... more MONDO indexed instances of RESULT_ENTRY
        }
    }

    which represent a 'meta' S-P-O edge something like:

        ("UUID:c5d67629-ce16-41e9-8b35-e4acee04ed1f": "biolink:PhenotypicFeature")
            --["biolink:similar_to"]->("MONDO:0008807": "biolink:Disease")

    where "UUID:c5d67629-ce16-41e9-8b35-e4acee04ed1f" designates a set
    containing the aggregate set of input phenotype terms "HP:0002104" and "HP:0012378".

    Details about SemSimian identified supporting 'similarity' edges are also returned
    and enumerated in an auxiliary graph associated with the UUID 'meta' similarity edge result.

    :param result: RESULT, SemSimian subject - object identifier mapping dataset with some metadata annotation
    :return: query result contents of the TRAPI Response.Message body (KnowledgeGraph, AuxGraph and Results added)
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
    #               "is_set": true,
    #               "set_interpretation": "OR+"
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
    # Add the following output parts (for one MONDO disease mapping):
    #
    #     "knowledge_graph": {
    #         "nodes": {
    #             "HP:0002104": {
    #                 "name": "Apnea (HPO)",
    #                 "categories": ["biolink:PhenotypicFeature"]
    #             },
    #             "HP:0012378": {
    #                 "name": "Fatigue (HPO)",
    #                 "categories": ["biolink:PhenotypicFeature"]
    #             },
    #             "UUID:c5d67629-ce16-41e9-8b35-e4acee04ed1f": {
    #                 "members": ["HP:0002104","HP:0012378"],
    #                 "categories": ["biolink:PhenotypicFeature"],
    #                 "is_set": true
    #             },
    #             "MONDO:0008807": {
    #                 "name": "obsolete apnea,
    #                 central sleep",
    #                 "categories": ["biolink:Disease"]
    #             }
    #         },
    #         "edges": {
    #             "e01": {
    #                 "subject": "UUID:c5d67629-ce16-41e9-8b35-e4acee04ed1f",
    #                 "predicate": "biolink:similar_to",
    #                 "object": "MONDO:0008807",
    #                 "attributes": [],
    #                 "sources": [
    #                   {
    #                     "resource_id": "infores:semsimian-kp",
    #                     "resource_role": "primary_knowledge_source",
    #                     "source_record_urls": null,
    #                     "upstream_resource_ids": ["infores:hpo-annotations", "infores:upheno"]
    #                    },
    #                   {
    #                     "resource_id": "infores:hpo-annotations",
    #                     "resource_role": "supporting_data_source",
    #                     "source_record_urls": null,
    #                     "upstream_resource_ids": []
    #                    },
    #                   {
    #                     "resource_id": "infores:upheno",
    #                     "resource_role": "supporting_data_source",
    #                     "source_record_urls": null,
    #                     "upstream_resource_ids": []
    #                    }
    #                 ]
    #             },
    #
    # The additional edges below all relate to the FIRST pairwise match between
    # an input phenotype and a phenotype associated with the returned Disease,
    # derived from the following raw SemSimian 'similarity' output record:
    #
    # "object_best_matches": {
    #    "HP:0002104": {
    #       'match_source': 'HP:0002104',
    #       'match_source_label': 'Apnea (HPO)',
    #       'match_target': 'HP:0010535',
    #       'match_target_label': 'Sleep apnea (HPO)',
    #       'score': 14.887188876843995,
    #       'match_subsumer': None,
    #       'match_subsumer_label': None,
    #       'similarity': {
    #           'subject_id': 'HP:0002104',
    #           'subject_label': None,
    #           'subject_source': None,
    #           'object_id': 'HP:0010535',
    #           'object_label': None,
    #           'object_source': None,
    #           'ancestor_id': 'HP:0002104',
    #           'ancestor_label': 'Apnea (HPO)',
    #           'ancestor_source': None,
    #           'object_information_content': None,
    #           'subject_information_content': None,
    #           'ancestor_information_content': 14.887188876843995,
    #           'jaccard_similarity': 0.6470588235294118,
    #           'cosine_similarity': None,
    #           'dice_similarity': None,
    #           'phenodigm_score': 3.103689243515017
    #       }
    #    },
    # ... more matching edges...
    # }
    #
    # Giving the following sets of edges:
    #
    # e02: A support graph edge reporting one of many pairwise similarity assertions
    # between an input phenotype and a phenotype associated with the returned Disease
    #
    #             "e02": {
    #                 "subject": "HP:0002104",        # 'match_source' == 'Apnea (HPO)'
    #                 "predicate": "biolink:similar_to",
    #                 "object": "HP:0010535",         # 'match_target' == 'Sleep apnea (HPO)'
    #                 "sources": [
    #                    {
    #                         "resource_id": "infores:semsimian-kp",
    #                         "resource_role": "primary_knowledge_source",
    #                         "source_record_urls": null,
    #                         "upstream_resource_ids": ["infores:hpo-annotations", "infores:upheno"]
    #                    },
    #                    {
    #                         "resource_id": "infores:hpo-annotations",
    #                         "resource_role": "supporting_data_source",
    #                         "source_record_urls": null,
    #                         "upstream_resource_ids": []
    #                    },
    #                    {
    #                         "resource_id": "infores:upheno",
    #                         "resource_role": "supporting_data_source",
    #                         "source_record_urls": null,
    #                         "upstream_resource_ids": []
    #                    }
    #                  ],
    #                  "attributes": [
    #                     {
    #                         "attribute_type_id": "biolink:score",
    #                         "value": 14.887188876843995,
    #                         "value_type_id": "linkml:Float",
    #                         "attribute_source": "infores:semsimian-kp"
    #                     },
    #                     {
    #                         "attribute_type_id": "biolink:match",
    #                         "value": "HP:0010535"                 # 'ancestor_id' == 'Sleep apnea (HPO)'
    #                         "value_type_id": "linkml:Uriorcurie",
    #                         "attribute_source": "infores:semsimian-kp"
    #                     }
    #                 ]
    #             }
    #
    # The aggregate (UUID 'meta') edge is the core result, but other edges serve
    # as supporting edges (evidence) recorded in the auxiliary graph, as follows:
    #
    #
    #     "auxiliary_graphs": {
    #         "auxgraph001": {
    #             "edges": [
    #                 "e02",
    #                 "e03",
    #                 "e04",
    #                 "e05",
    #                 "e06",
    #                 "e07"
    #             ]
    #         }
    #     }
    #
    # Corresponding with result
    #
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
    ingest_knowledge_source: str = result["ingest_knowledge_source"]
    common_sources: List[Dict] = [
        {
            "resource_id": primary_knowledge_source,
            "resource_role": "primary_knowledge_source"
        },
        {
            "resource_id": ingest_knowledge_source,
            "resource_role": "supporting_data_source"
        }
    ]
    subject_id: str
    result_map: RESULTS_MAP = result["result_map"]
    reset_edge_idx()
    for subject_id, result_entry in result_map.items():

        # 1. Add the "nodes" to the "knowledge_graph" - if not already present
        if subject_id not in trapi_response["knowledge_graph"]["nodes"]:
            subject_name = result_entry["name"]
            subject_category = result_entry["category"]
            trapi_response["knowledge_graph"]["nodes"][subject_id] = {
                "name": subject_name,
                "categories": get_categories(category=subject_category)
            }

        # Build the shared 'sources' provenance block
        sources: List[Dict] = deepcopy(common_sources)
        if "provided_by" in result_entry:
            sources.append(
                {
                    "resource_id": result_entry["provided_by"],
                    "resource_role": "supporting_data_source"
                }
            )

        # 2. Need to create the overall "results" list entry
        #    for this similarity match, so that it can be
        #    populated concurrently with the knowledge_graph edges
        matched_terms: MATCH_LIST = result_entry["matches"]
        term_data: TERM_DATA
        trapi_results_entry: Dict = {
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
            #                 "subject": "HP:0002104",
            #                 "predicate": "biolink:similar_to",
            #                 "object": "MONDO:0008807",
            #                 "sources": [
            #                     {
            #                         "resource_id": "infores:semsimian-kp-kp",
            #                         "resource_role": "primary_knowledge_source",
            #                         "source_record_urls": null,
            #                         "upstream_resource_ids": ["infores:hpoa", "infores:upheno"]
            #                     },
            #                     {
            #                         # Ingest Knowledge Source (Monarch curator hardcode-specified)
            #
            #                         "resource_id": "infores:hpo-annotations",
            #                         "resource_role": "supporting_data_source",
            #                         "source_record_urls": null,
            #                         "upstream_resource_ids": []
            #                     },
            #                     {
            #                         # SemSimian entry 'provided_by' specified Knowledge Source
            #
            #                         "resource_id": "infores:upheno",
            #                         "resource_role": "supporting_data_source",
            #                         "source_record_urls": null,
            #                         "upstream_resource_ids": []
            #                     }
            #                 ],
            #                 "attributes": [
            #                     {
            #                         "attribute_type_id": "biolink:score",
            #                         "value": 9.959829749061718,
            #                         "value_type_id": "linkml:Float",
            #                         "attribute_source": "infores:semsimian-kp"
            #                     },
            #                     {
            #                         "attribute_type_id": "biolink:support_graphs",
            #                         "value": ["ag-e01"],
            #                         "value_type_id": "linkml:String",
            #                         "attribute_source": "infores:semsimian-kp"
            #                     }
            #                 ]
            #             }
            edge_id = next_edge_id()
            # Note here that n0 are the subject but come from the SemSimian object terms
            trapi_response["knowledge_graph"]["edges"][edge_id] = {
                "subject": term_data["id"],
                "predicate": "biolink:similar_to",
                "object": subject_id,
                "attributes": [

                ],
                "sources": deepcopy(sources)
            }

            # 4. TODO: Capture the contents of the "auxiliary_graph" here?
            #
            #     "auxiliary_graphs": {
            #         "ag-e01": {
            #             "edges": [
            #                 "e02",
            #                 "e03",
            #                 "e04",
            #                 "e05",
            #                 "e06",
            #                 "e07"
            #             ]
            #         }
            #     },

            # 5. ...then track the new edge as a specific "result" entry for the QEdge
            trapi_results_entry["analyses"][0]["edge_bindings"]["e01"].append({"id": edge_id})

        # Create UUID aggregate set node for the TRAPI response
        # TODO: the matched_terms set may be replicated for all subject_id matches...
        #       It seems redundant to generate a fresh UUID every time?
        input_set_uuid = f"UUID:{str(uuid4())}"
        category_set: Set[str] = set()
        for term_data in matched_terms:
            category_set.update(get_categories(category=term_data["category"]))
        trapi_response["knowledge_graph"]["nodes"][input_set_uuid] = {
            "members": [term_data["id"] for term_data in matched_terms],
            "categories": list(category_set),
            "is_set": True
        }

        trapi_response["results"].append(trapi_results_entry)

    return trapi_response
