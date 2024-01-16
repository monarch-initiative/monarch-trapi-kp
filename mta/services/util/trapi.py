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

edge_idx = 0


def reset_edge_idx():
    global edge_idx
    edge_idx = 0


def next_edge_id() -> str:
    global edge_idx
    edge_idx += 1
    return f"e{edge_idx:0>3}"


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


def is_subject_qnode(node_data: Dict) -> bool:
    return True if "is_set" in node_data and node_data["is_set"] and \
            "set_interpretation" in node_data and node_data["set_interpretation"] == "OR+" and \
            "ids" in node_data else False


def build_trapi_message(
        trapi_message: Dict,
        result: RESULT
) -> Dict:
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

    :param trapi_message: Dict, input TRAPI Message (Query Graph)
    :param result: RESULT, SemSimian subject - object identifier mapping dataset with some metadata annotation
    :return: query result contents of the TRAPI Response.Message body (KnowledgeGraph, AuxGraph and Results added)
    """
    # Statement results as noted above, from the original QGraph, assumed to be somewhat of form:
    #
    # "query_graph": {
    #       "nodes": {
    #         "phenotypes": {
    #           "categories": [
    #             "biolink:PhenotypicFeature"
    #           ],
    #           "ids": [
    #             "HP:0002104",
    #             "HP:0012378"
    #           ],
    #           "is_set": true,
    #           "set_interpretation": "OR+"
    #         },
    #         "diseases": {
    #           "categories": [
    #             "biolink:Disease"
    #           ]
    #         }
    #       },
    #       "edges": {
    #         "e01": {
    #               "subject": "n0",
    #               "object": "n1",
    #               "predicates": [
    #                     "biolink:similar_to"
    #               ]
    #         }
    #       }
    #   }
    #
    # Code to extract (meta-)data from the TRAPI message

    nodes: Dict = trapi_message["query_graph"]["nodes"]
    qnode_id: str
    details: Dict
    qnode_subject_key: str = "n0"
    qnode_object_key: str = "n1"

    for qnode_id, node_data in nodes.items():
        if is_subject_qnode(node_data):
            qnode_subject_key = qnode_id
        else:
            qnode_object_key = qnode_id

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
    #             "e001": {
    #                     "subject": "UUID:c5d67629-ce16-41e9-8b35-e4acee04ed1f",
    #                     "predicate": "biolink:similar_to",
    #                     "object": "MONDO:0015317",
    #                     "sources": [
    #                       {
    #                        "resource_id": "infores:semsimian-kp",
    #                        "resource_role": "primary_knowledge_source",
    #                        "source_record_urls": null,
    #                        "upstream_resource_ids": ["infores:hpoa", "infores:upheno"]
    #                       },
    #                       {
    #                        "resource_id": "infores:hpo-annotations",
    #                        "resource_role": "supporting_data_source",
    #                        "source_record_urls": null,
    #                        "upstream_resource_ids": []
    #                       },
    #                      {
    #                       "resource_id": "infores:upheno",
    #                       "resource_role": "supporting_data_source",
    #                       "source_record_urls": null,
    #                       "upstream_resource_ids": []
    #                      }
    #                    ],
    #                     "attributes": [
    #                       {
    #                           "attribute_type_id": "biolink:score",
    #                           "value": 13.074943444390097,  # RESULT_MAPS-level 'score'
    #                           "value_type_id": "linkml:Float",
    #                           "attribute_source": "infores:semsimian-kp"
    #                       },
    #                       {
    #                           # auxiliary_graph 'Support Graph' ('sg')
    #                           # associated with this 'answer' edge 'e001'
    #                           "attribute_type_id": "biolink:support_graphs",
    #                           "value": ["sg-e001"],
    #                           "value_type_id": "linkml:String",
    #                           "attribute_source": "infores:semsimian-kp"
    #                       },
    #                     ]
    #                   }
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
    # Giving the following sets of additional supporting edges:
    #
    # e002: A support graph edge reporting one of many pairwise similarity assertions
    # between an input phenotype and a phenotype associated with the returned Disease
    #
    # "e002": {
    #     "subject": "HP:0012378",        # 'match_source' == 'Fatigue (HPO)'
    #     "predicate": "biolink:similar_to",
    #     "object": "HP:0001699",         # 'match_target' == 'Sudden death (HPO)'
    #     "sources": [
    #        {
    #             "resource_id": "infores:semsimian-kp",
    #             "resource_role": "primary_knowledge_source",
    #             "source_record_urls": null,
    #             "upstream_resource_ids": ["infores:hpo-annotations", "infores:upheno"]
    #        },
    #        {
    #             "resource_id": "infores:hpo-annotations",
    #             "resource_role": "supporting_data_source",
    #             "source_record_urls": null,
    #             "upstream_resource_ids": []
    #        },
    #        {
    #             "resource_id": "infores:upheno",
    #             "resource_role": "supporting_data_source",
    #             "source_record_urls": null,
    #             "upstream_resource_ids": []
    #        }
    #      ],
    #      "attributes": [
    #         {
    #             "attribute_type_id": "biolink:score",
    #             "original_attribute_name": "semsimian:object_best_matches.*.score",
    #             "value": 11.262698011936202,
    #             "value_type_id": "linkml:Float",
    #             "attribute_source": "infores:semsimian-kp"
    #         },
    #         {
    #             "attribute_type_id": "biolink:match",
    #             "original_attribute_name": "semsimian:object_best_matches.*.similarity.ancestor_id",

    #             # Note: sometimes the 'ancestor_label' == 'Constitutional symptom', is missing?

    #             # TODO: Likely have to look this term up on HPO and
    #             #       add it to the node catalog (is this necessary?)
    #             "value": "HP:0025142"  # this is the common subsumer a.k.a. 'ancestor_id'
    #             "value_type_id": "linkml:Uriorcurie",
    #             "attribute_source": "infores:semsimian-kp"
    #         }
    #     ]
    # }
    #
    #  e003: A support graph edge reporting the matched phenotype
    #  in the pairwise similarity edge above to be associated
    #  with the Disease result.
    #
    #  "e003": {
    #     "object": "HP:0001699",               # 'match_target' == 'Sudden death (HPO)'
    #     "predicate": "biolink:phenotype_of",
    #     "subject": "MONDO:0008807",           # 'subject.name' == 'obsolete apnea, central sleep' (Disease)
    #     "sources": [
    #           {
    #             "resource_id": "infores:hpo-annotations",
    #             "resource_role": "primary_knowledge_source",
    #             "source_record_urls": None,
    #             "upstream_resource_ids": []
    #            },
    #           {
    #             "resource_id": "infores:monarch-initiative",
    #             "resource_role": "aggregator_knowledge_source",
    #             "source_record_urls": None,
    #             "upstream_resource_ids": ["infores:hpo-annotations"]
    #            },
    #      "attributes": [
    #        	{
    #             "attribute_type_id": "biolink:has_evidence",
    #               # ECO code for 'author statement supported by
    #               # traceable reference used in manual assertion'
    #             "value": "ECO:0000304",
    #             "value_type_id": "linkml:Uriorcurie",
    #             "attribute_source": "infores:hpo-annotations"
    #        	},
    #        	{
    #             "attribute_type_id": "biolink:publications",
    #             # TODO: this would be a supporting HPOA publication
    #             #       referenced by (and retrieved from?) Monarch,
    #             #       linking the phenotype with its disease.
    #             "value": ["orphanet:137935"]    # this is an illustrative by mismatched publication for this edge
    #             "value_type_id": "linkml:Uriorcurie",
    #             "attribute_source": "infores:hpo-annotations"
    #        	}
    #     ]
    # }
    #
    # e004: The following support graph edge reporting the input phenotype in
    # the pairwise similarity edge above to be a member of the input phenotype set.
    # This is obvious/trivial, so we may not need to report it.  But it makes the
    # visualized support graph more complete/intuitive
    #
    #   "e004": {
    #     "subject": "HP:0012378",        # 'match_source' == 'Fatigue (HPO)'
    #     "predicate": "biolink:member_of",
    #
    #     # The generated UUID for the input phenotype set
    #     "object": "UUID:c5d67629-ce16-41e9-8b35-e4acee04ed1f,
    #
    #     "sources": [
    #       {
    #           "resource_id": "infores:semsimian-kp",
    #        	"resource_role": "primary_knowledge_source",
    #        	"source_record_urls": null,
    #        	"upstream_resource_ids": []
    #        }
    #     ]
    #   }
    #
    # The aggregate (UUID 'meta') edge is the core result, but other edges serve
    # as supporting edges (evidence) recorded, as follows:
    #
    #     # auxiliary_graph 'Support Graph' ('sg')
    #     # associated with the 'answer' edge 'e001'
    #     "auxiliary_graphs": {
    #         "sg-e001": {
    #             "edges": [
    #                 "e002",
    #                 "e003",
    #                 "e004",
    #               etc... (supporting edges for all phenotype matches...)
    #             ]
    #         }
    #     }
    #
    # Corresponding with result
    #
    #     "results": [
    #         {
    #             "node_bindings": {
    #                 "phenotypes": [
    #                     {
    #                         "id": "UUID:c5d67629-ce16-41e9-8b35-e4acee04ed1f"
    #                     }
    #                 ],
    #                 "diseases": [
    #                     {
    #                         "id": "MONDO:0005148"
    #                     }
    #                 ]
    #             },
    #             "analyses": [
    #                 {
    #                     "resource_id": "infores:monarchinitiative",
    #                     "edge_bindings": {
    #                         "e01": [{"id": "e001"}]
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

        # sanity check to ensure that all lists with
        # identical terms, give an identical "matched_terms_key"
        matched_terms: List[str] = [term_data["subject_id"] for term_data in matches]
        matched_terms.sort()
        matched_terms_key = ",".join(matched_terms)

        # Create UUID aggregate set node for the TRAPI response.
        # Assume that one unique UUID is created for each
        # strict subset of input terms that are matched.
        query_set_uuid: str
        if matched_terms_key not in node_map:

            query_set_uuid = f"UUID:{str(uuid4())}"

            members: Set[str] = set()
            category_set: Set[str] = set()
            for term_data in matches:
                members.add(term_data["subject_id"])
                category_set.update(get_categories(category=term_data["category"]))

            node_map[matched_terms_key] = {
                "id": query_set_uuid,  # this will be the real node identifier later
                "members": list(members),
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
        #                "original_attribute_name": "semsimian:score",
        #               "value": 13.074943444390097,  # RESULT_MAPS-level 'score'
        #               "value_type_id": "linkml:Float",
        #               "attribute_source": "infores:semsimian-kp"
        #           },
        #           {
        #               # auxiliary_graph 'Support Graph' ('sg')
        #               # associated with this 'answer' edge 'e001'
        #               "attribute_type_id": "biolink:support_graphs",
        #               "value": ["sg-e001"],
        #               "value_type_id": "linkml:String",
        #               "attribute_source": "infores:semsimian-kp"
        #           },
        #         ]
        #       }

        # Identifier of the core similarity 'answer' edge mapping the
        # (UUID-identified) multi-curie subset of query (HPO) input terms
        # onto the term profile matched node (e.g. MONDO "disease")
        edge_id: str = next_edge_id()
        aux_graph_id: str = f"sg-{edge_id}"

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
                  "original_attribute_name": "semsimian:score",
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

        for term_data in matches:
            term_subject_id: str = term_data["subject_id"]
            # add matched term uniquely to nodes set
            if term_subject_id not in node_map:
                node_map[term_subject_id] = {
                    "id": term_subject_id,
                    "name": term_data["subject_name"],
                    "categories": get_categories(category=term_data["category"])
                }

            # Add the "edges" to the "knowledge_graph"...something like this:
            #
            #         "edges": {
            #             "e02": {
            #                 "subject": "HP:0002104",
            #                 "predicate": "biolink:phenotype_of",
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
            #                 "attributes": [ xxxx wrong set of attributes - see ex:Edge003 instead
            #                     {
            #                         "attribute_type_id": "biolink:has_evidence",
            #                         "value": "ECO:0000304",
            #                         # ECO code for 'author statement supported by
            #                         # traceable reference used in manual assertion'
            #                         "value_type_id": "linkml:Uriorcurie",
            #                         "attribute_source": "infores:hpoa"
            #                     },
            #                     {
            #                         "attribute_type_id": "biolink:publications",
            #                         # a supporting publication referenced by HPOA/Monarch(?)
            #                         "value": ["orphanet:137935"],
            #                         "value_type_id": "linkml:Uriorcurie",
            #                         "attribute_source": "infores:hpoa"
            #                     }
            #                 ]
            #             }
            term_edge_id = next_edge_id()
            # Note here that n0 are the subject but come from the SemSimian object terms
            trapi_response["knowledge_graph"]["edges"][term_edge_id] = {
                "subject": term_data["subject_id"],
                "predicate": "biolink:phenotype_of",
                "object": object_id,
                "sources": deepcopy(sources),
                "attributes": [
                    {
                        "attribute_type_id": "biolink:has_evidence",
                        "value": "ECO:0000304",
                        # ECO code for 'author statement supported by
                        # traceable reference used in manual assertion'
                        "value_type_id": "linkml:Uriorcurie",
                        "attribute_source": "infores:hpo-annotations"
                    },
                    # {
                    #     "attribute_type_id": "biolink:publications",
                    #     # a supporting publication referenced by HPOA/Monarch(?)
                    #     "value": ["orphanet:137935"],
                    #     "value_type_id": "linkml:Uriorcurie",
                    #     "attribute_source": "infores:hpoa"
                    # }
                ],

            }

            # 4. TODO: Capture the contents of the "auxiliary_graph" here?
            #
            #     "auxiliary_graphs": {
            #         "sg-e001": {
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

        # "results" list entry for the current "object_id" similarity match
        trapi_results_entry: Dict = {
            "node_bindings": {
                qnode_subject_key: [{"id": query_set_uuid}],
                qnode_object_key: [{"id": object_id}]
            },
            "analyses": [
                {
                    "resource_id": "infores:monarchinitiative",
                    "edge_bindings": {"e01": [{"id": edge_id}]}
                }
            ]
        }
        trapi_response["results"].append(trapi_results_entry)

    # Deferred loading of the knowledge map nodes dictionary
    node_details: Dict
    for key, node_details in node_map.items():
        qnode_id: str = node_details.pop("id")
        trapi_response["knowledge_graph"]["nodes"][qnode_id] = node_details

    return trapi_response
