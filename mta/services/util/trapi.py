"""
TRAPI JSON accessing data utilities.
This module knows about the TRAPI syntax such that it can
extract parameters and build TRAPI Responses from results
"""
from typing import Optional, Tuple, List, Dict, Set
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
    # Statement results as noted above, from the original QGraph, assumed to be somewhat of form:
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

    # First, initialize a stub template for the TRAPI Response
    trapi_response: Dict = {
        "knowledge_graph": {
            "nodes": {},
            "edges": {}
        },
        "auxiliary_graphs": {},
        "results": []
    }

    # Then, add TRAPI Response parts somewhat like the following (spanning each similarity mapping):
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
    #            ...etc... see the additional edges below
    #
    # The additional edges below all relate to the pairwise match between
    # each input phenotype and a phenotype associated with the returned Disease,
    # derived from the following SemSimian 'object_best_matches.similarity' data:
    #
    # "object_best_matches": {
    #    "HP:0012378": {
    #       'match_source': 'HP:0012378',
    #       'match_source_label': 'Fatigue (HPO)',
    #       'match_target': 'HP:0001699',
    #       'match_target_label': 'Sudden death (HPO)',
    #       'score': 11.262698011936202,
    #       'match_subsumer': None,
    #       'match_subsumer_label': None,
    #       'similarity': {
    #           'subject_id': 'HP:0012378',
    #           'subject_label': None,
    #           'subject_source': None,
    #           'object_id': 'HP:0001699',
    #           'object_label': None,
    #           'object_source': None,
    #           'ancestor_id': 'HP:0025142',
    #           'ancestor_label': '',
    #           'ancestor_source': None,
    #           'object_information_content': None,
    #           'subject_information_content': None,
    #           'ancestor_information_content': 11.262698011936202,
    #           'jaccard_similarity': 0.8461538461538461,
    #           'cosine_similarity': None,
    #           'dice_similarity': None,
    #           'phenodigm_score': 3.0870657979494207
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
    object_id: str
    node_map: Dict = dict()
    result_map: RESULTS_MAP = result["result_map"]
    reset_edge_idx()

    for object_id, result_entry in result_map.items():

        # Capture the primary answer node object matched
        if object_id not in node_map:
            node_map[object_id] = {
                "id": object_id,
                "name": result_entry["name"],
                "categories": get_categories(category=result_entry["category"])
            }

        # RESULT_MAPS-level answer 'score'
        answer_score = result_entry["score"]

        # Complete the shared 'sources' provenance block
        sources: List[Dict] = deepcopy(common_sources)
        if "provided_by" in result_entry:
            sources.append(
                {
                    "resource_id": result_entry["provided_by"],
                    "resource_role": "supporting_data_source"
                }
            )

        # Extract the various terms matched from the query
        matches: MATCH_LIST = result_entry["matches"]
        term_data: TERM_DATA
        matched_terms: List[str] = [term_data["subject_id"] for term_data in matches]

        # sanity check to ensure that all lists with
        # identical terms, give an identical matched_terms_key
        matched_terms.sort()
        matched_terms_key = ",".join(matched_terms)

        # Create UUID aggregate set node for the TRAPI response.
        # Assume that one unique UUID is created for each sequence of
        query_set_uuid: str
        if matched_terms_key not in node_map:
            query_set_uuid = f"UUID:{str(uuid4())}"
            category_set: Set[str] = set()
            for term_data in matched_terms:
                category_set.update(get_categories(category=term_data["category"]))
            node_map[matched_terms_key] = {
                "id": query_set_uuid,  # this will be the real node identifier later
                "members": [term_data["id"] for term_data in matched_terms],
                "categories": list(category_set),
                "is_set": True
            }
        else:
            query_set_uuid = node_map[matched_terms_key]["id"]

        # Add the 'answer edge', directly reporting that the input term
        # (UUID) set is similar (phenotypically) to a particular Disease
        #
        # "e1": {
        #         "subject": "UUID:c5d67629-ce16-41e9-8b35-e4acee04ed1f",
        #         "predicate": "biolink:similar_to",
        #         "object": "MONDO:0015317",
        #         "sources": [
        #           {
        #            "resource_id": "infores:semsimian-kp",
        #            "resource_role": "primary_knowledge_source",
        #            "source_record_urls": null,
        #            "upstream_resource_ids": ["infores:hpoa", "infores:upheno"]
        #           },
        #           {
        #            "resource_id": "infores:hpo-annotations",
        #        	   "resource_role": "supporting_data_source",
        #        	   "source_record_urls": null,
        #        	   "upstream_resource_ids": []
        #           },
        #          {
        #           "resource_id": "infores:upheno",
        #           "resource_role": "supporting_data_source",
        #        	  "source_record_urls": null,
        #        	  "upstream_resource_ids": []
        #          }
        #        ],
        #         "attributes": [
        #           {
        #               "attribute_type_id": "biolink:score",
        #               "value": 13.074943444390097,  # RESULT_MAPS-level 'score'
        #               "value_type_id": "linkml:Float",
        #               "attribute_source": "infores:semsimian-kp"
        #           },
        #           {
        #               # auxiliary_graph associated with this 'answer' edge 'e1'
        #               "attribute_type_id": "biolink:support_graphs",
        #               "value": ["ag-e1"],
        #               "value_type_id": "linkml:String",
        #               "attribute_source": "infores:semsimian-kp"
        #           },
        #         ]
        #       }
        edge_id: str = next_edge_id()
        aux_graph_id: str = f"ag-{edge_id}"
        trapi_response["auxiliary_graphs"][aux_graph_id] = {"edges": []}

        # Note here that n0 are the subject but come from the SemSimian object terms
        trapi_response["knowledge_graph"]["edges"][edge_id] = {
            "subject": query_set_uuid,
            "predicate": "biolink:similar_to",
            "object": object_id,
            "sources": deepcopy(sources),
            "attributes": [
                {
                  "attribute_type_id": "biolink:score",
                  "value": answer_score,
                  "value_type_id": "linkml:Float",
                  "attribute_source": "infores:semsimian-kp"
                },
                {
                  "attribute_type_id": "biolink:support_graphs",
                  "value": [aux_graph_id],
                  "value_type_id": "linkml:String",
                  "attribute_source": "infores:semsimian-kp"
                }
            ]
        }

        # "results" list entry for each "object_id" similarity match
        # TODO: review if there are multiple entries here, one per UUID - object_id mapping?
        trapi_results_entry: Dict = {
            "node_bindings": {
                "n0": [{"id": query_set_uuid}],
                "n1": [{"id": object_id}]
            },
            "analyses": [
                {
                    "resource_id": "infores:monarchinitiative",
                    "edge_bindings": {"e01": [{"id": edge_id}]}
                }
            ]
        }

        for term_data in matched_terms:
            term_subject_id: str = term_data["subject_id"]
            # add matched term uniquely to nodes set
            if term_subject_id not in node_map:
                node_map[term_subject_id] = {
                    "id": term_subject_id,
                    "name": term_data["subject_name"],
                    "categories": get_categories(category=term_data["category"])
                }

            # Add the "edges" to the "knowledge_graph"...

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
            term_edge_id = next_edge_id()
            # Note here that n0 are the subject but come from the SemSimian object terms
            trapi_response["knowledge_graph"]["edges"][term_edge_id] = {
                "subject": term_data["id"],
                "predicate": "biolink:similar_to",
                "object": object_id,
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
            trapi_response["auxiliary_graphs"][aux_graph_id]["edges"].append(term_edge_id)

        # Load the knowledge map nodes dictionary
        node_details: Dict
        for key, node_details in node_map:
            node_id: str = node_details.pop("id")
            trapi_response["knowledge_graph"]["nodes"][node_id] = node_details

        trapi_response["results"].append(trapi_results_entry)

    return trapi_response
