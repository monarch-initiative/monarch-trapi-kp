"""
TRAPI JSON accessing data utilities.
This module knows about the TRAPI syntax such that it can
extract parameters and build TRAPI Responses from results
"""
from typing import Optional, List, Dict
from functools import lru_cache
from copy import deepcopy
from mmcq.services.util import (
    TERM_DATA,
    MATCH_LIST,
    RESULTS_MAP,
    RESULT
)
from bmt import Toolkit

# Synthetic 'original_attribute_name' for SemSimian attributes
AGGREGATE_SIMILARITY_SCORE = "semsimian:score"
MATCH_TERM_SCORE = "semsimian:object_best_matches.*.score"
MATCH_TERM = "semsimian:object_best_matches.*.similarity.ancestor_id"

edge_idx = 0


def reset_edge_idx():
    global edge_idx
    edge_idx = 0


def next_edge_id() -> str:
    global edge_idx
    edge_idx += 1
    return f"e{edge_idx:0>4}"


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


def is_mcq_subject_qnode(node_data: Dict) -> bool:
    return "is_set" in node_data and node_data["is_set"] and \
           "set_interpretation" in node_data and node_data["set_interpretation"] and \
           node_data["set_interpretation"] in ["MANY", "ALL"] and \
           "ids" in node_data and node_data["ids"] and \
           "member_ids" in node_data and node_data["member_ids"]


def build_trapi_message(
        trapi_message: Dict,
        result: RESULT,
        provenance: str
) -> Dict:
    """
    Uses the object id indexed list of subjects to build the internal message contents of the knowledge graph.
    Input result is a RESULT dictionary of format looking somewhat like:
    {
        "set_interpretation": "MANY",
        "set_identifier": "UUID:4403ddf2-f724-4b3b-a877-de08315b784f",
        "query_terms": [
                "HP:0002104",
                "HP:0012378"
        ],
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
    :param provenance: str, default global provenance for the system result
    :return: query result contents of the TRAPI Response.Message body (KnowledgeGraph, AuxGraph and Results added)
    """
    # Statement results as noted above, from the original QGraph,
    # for a phenotypes to disease similarity query,
    # is assumed to be somewhat of the follow format:
    #
    # "query_graph": {
    #   "nodes": {
    #     "phenotypes": {
    #       "categories": [
    #         "biolink:PhenotypicFeature"
    #       ],
    #       "ids": ["UUID:4403ddf2-f724-4b3b-a877-de08315b784f"],
    #       "member_ids": [
    #         "HP:0002104",
    #         "HP:0012378"
    #       ],
    #       "is_set": true,
    #       "set_interpretation": "MANY"
    #     },
    #     "diseases": {
    #       "categories": [
    #         "biolink:Disease"
    #       ]
    #     }
    #   },
    #   "edges": {
    #     "e01": {
    #       "subject": "phenotypes",
    #       "object": "diseases",
    #       "predicates": [
    #         "biolink:similar_to"
    #       ]
    #     }
    #   }
    # }
    #

    # Code to extract (meta-)data from the TRAPI Request Message Query Graph
    nodes: Dict = trapi_message["query_graph"]["nodes"]
    qnode_id: str
    node_data: Dict
    qnode_subject_key: str = "n0"
    qnode_object_key: str = "n1"

    # TODO: we expect only be two defined query nodes.
    #       Would it problematic otherwise?
    #       Should this be checked earlier?
    for qnode_id, node_data in nodes.items():
        if is_mcq_subject_qnode(node_data):
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

    # Then, add TRAPI Response parts somewhat like
    # the following sample Phenotype-to-Disease mappings
    # (spanning each similarity mapping):
    #
    #     "knowledge_graph": {
    #         "nodes":

    #             "e001": {
    #                     "subject": "UUID:4403ddf2-f724-4b3b-a877-de08315b784f",
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
    #                           "original_attribute_name": "semsimian:score",
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
    #                       {
    #                           "attribute_type_id": "biolink:agent_type",
    #                           "value": "automated_agent",
    #                       },
    #                       {
    #                           "attribute_type_id": "biolink:knowledge_level",
    #                           "value": "knowledge_assertion",
    #                       }
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
    # Giving the following sets of additional "support graph" edges:
    #
    # e002: A support graph edge reporting one of many pairwise similarity assertions
    #       between an input query phenotype and a phenotype associated with a returned Disease.
    #
    # "e002": {
    #     "subject": "HP:0012378",        # similarity 'match_source' == 'Fatigue (HPO)'
    #     "predicate": "biolink:similar_to",
    #     "object": "HP:0001699",         # similarity 'match_target' == 'Sudden death (HPO)'
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
    #
    #             # Note: sometimes the 'ancestor_label' == 'Constitutional symptom', is missing?
    #
    #             # TODO: Likely have to look this term up on HPO and
    #             #       add it to the node catalog (is this necessary?)
    #             "value": "HP:0025142"  # this is the common subsumer a.k.a. 'ancestor_id'
    #             "value_type_id": "linkml:Uriorcurie",
    #             "attribute_source": "infores:semsimian-kp"
    #         },
    #         {
    #             "attribute_type_id": "biolink:agent_type",
    #             "value": "automated_agent",
    #         },
    #         {
    #             "attribute_type_id": "biolink:knowledge_level",
    #             "value": "knowledge_assertion",
    #         }
    #     ]
    # }
    #
    #  e003: A support graph edge reporting the matched phenotype in the
    #        pairwise similarity edge above to be associated with the Disease result.
    #
    #  "e003": {
    #     "object": "HP:0001699",               # 'match_target_label' == 'Sudden death (HPO)'
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
    #             "resource_id": "infores:monarchinitiative",
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
    #             "value": ["orphanet:137935"]    # this is an illustrative by mismatched publication for this edge
    #             "value_type_id": "linkml:Uriorcurie",
    #             "attribute_source": "infores:hpo-annotations"
    #        	},
    #           {
    #             "attribute_type_id": "biolink:agent_type",
    #             "value": "automated_agent",
    #           },
    #           {
    #             "attribute_type_id": "biolink:knowledge_level",
    #             "value": "knowledge_assertion",
    #           }
    #     ]
    # }
    #
    # e004: The following support graph edge reporting the input phenotype in the
    #       pairwise-similarity edge above, to be a member of the input phenotype set.
    #       This is obvious/trivial, so we may not need to report it.
    #       But it makes the visualized support graph more complete/intuitive.
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
    #                         "id": "UUID:4403ddf2-f724-4b3b-a877-de08315b784f"
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
    #                     "resource_id": DEFAULT_PROVENANCE,
    #                     "edge_bindings": {
    #                         "e01": [{"id": "e001"}]
    #                     }
    #                 }
    #             ]
    #         }
    #     ]
    # }

    set_interpretation: str = result["set_interpretation"]
    input_query_set_id: str = result["set_identifier"]
    query_terms: List[str] = result["query_terms"]
    query_term_category: str = result["query_term_category"]
    primary_knowledge_source: str = result["primary_knowledge_source"]
    ingest_knowledge_source: str = result["ingest_knowledge_source"]
    match_predicate: str = result["match_predicate"]

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

    matched_term_id: str
    node_map: Dict = dict()
    reset_edge_idx()
    query_term_membership_edges: Dict[str, str] = dict()

    ################################################################################################
    #
    # DEPRECATED: this January 2024 code moved elsewhere, below, with some modification.
    #
    # for matched_term_id, result_entry in result_map.items():
    #
    #     # Capture the primary answer node object matched
    #     if matched_term_id not in node_map:
    #         node_map[matched_term_id] = {
    #             "id": matched_term_id,
    #             "name": result_entry["name"],
    #             "categories": get_categories(category=result_entry["category"]),
    #             "is_set": False
    #         }
    #
    #     # RESULT_MAPS-level answer 'score'
    #     answer_score = result_entry["score"]
    #
    #     # Complete the shared 'sources' provenance block
    #     sources: List[Dict] = deepcopy(common_sources)
    #     if "provided_by" in result_entry:
    #         sources.append(
    #             {
    #                 "resource_id": result_entry["provided_by"],
    #                 "resource_role": "supporting_data_source"
    #             }
    #         )
    #
    #     # Extract the various terms matched from the query
    #     matches: MATCH_LIST = result_entry["matches"]
    #     term_data: TERM_DATA
    #
    # TODO: I need to fix this here to use the supplied 'result["set_identifier"]'
    #       and relate this to the original 'query_terms' set, with postprocessing of the
    #       'result_map' driven by the stipulated 'set_interpretation' ("MANY" versus "ALL")
    #
    # DEPRECATED: January 2024 prototype assumed that one unique UUID is created
    #             for each and every strict subset of input terms that are matched.
    #             This is no longer true: just the original input query terms are
    #             designated by a (single) node with a UUID, and the set defined by
    #             'member_of' edges, then individual subject_id nodes are linked to
    #             their diseases directly via 'phenotype_of' or indirectly via a transitive
    #             subgraph 'similar_to' -> <other phenotype> -> 'phenotype_of' <disease>.
    #
    #     # Sanity check to ensure that all lists with
    #     # identical terms, give an identical "matched_terms_key"
    #     matched_terms: List[str] = [term_data["subject_id"] for term_data in matches]
    #     matched_terms.sort()
    #     matched_terms_key = ",".join(matched_terms)
    #
    #     # Create UUID identifier for node representing the set of input query terms.
    #
    #     query_set_uuid: str
    #     if matched_terms_key not in node_map:
    #         query_set_uuid = f"UUID:{str(uuid4())}"
    #         members: Set[str] = set()
    #         category_set: Set[str] = set()
    #         for term_data in matches:
    #             query_term: str = term_data["subject_id"]
    #             members.add(query_term)
    #             category_set.update(get_categories(category=term_data["category"]))
    #
    #             # e004: The following support graph edges reporting the input terms in the
    #             #       pairwise-similarity edge above, to be a member of the query terms set.
    #             #       This is obvious/trivial, so we may not need to report it.
    #             #       But it makes the visualized support graph more complete/intuitive.
    #             # TODO: double check "query_term_membership_edges" for correctness:
    #             #       does it deal properly with strict subsets of query_terms
    #             #       for a given matched_term_id, for a given UUID (the match_terms_key
    #             #       above ensures a unit UUID for each strict subset but maybe not for
    #             #       the "query_term_membership_edges" linked to the given UUID)?
    #             if query_term not in query_term_membership_edges:
    #                 e004_edge_id: str = next_edge_id()
    #                 trapi_response["knowledge_graph"]["edges"][e004_edge_id] = {
    #                     "subject": query_term,
    #                     "predicate": "biolink:member_of",
    #                     "object": query_set_uuid,
    #                     "sources": [
    #                         {
    #                             "resource_id": primary_knowledge_source,
    #                             "resource_role": "primary_knowledge_source"
    #                         }
    #                     ]
    #                 }
    #                 query_term_membership_edges[query_term] = e004_edge_id
    #
    #         node_map[matched_terms_key] = {
    #             "id": query_set_uuid,  # this will be the real node identifier later
    #             "members": list(members),
    #             "categories": list(category_set),
    #             "is_set": True
    #         }
    #
    #     else:
    #         query_set_uuid = node_map[matched_terms_key]["id"]
    ################################################################################################

    ################################################################################################
    #
    # May 2024 MMCQ implementation
    #
    # 1.  Define knowledge graph nodes
    # 2.  Define knowledge graph edges
    #
    # 1.1 A node object representing the input query term set, identified by its UUID
    #
    #     "UUID:4403ddf2-f724-4b3b-a877-de08315b784f": {
    #         "members": ["HP:0002104","HP:0012378"],
    #         "categories": ["biolink:PhenotypicFeature"],
    #         "is_set": True
    #     },
    #
    node_map[input_query_set_id] = {
        "id": input_query_set_id,
        "members": query_terms.copy(),  # for safety, just use a copy of the original list
        "categories": get_categories(category=query_term_category),
        "is_set": True,
        "provided_by": ["infores:user-interface"]
    }

    for term_id in query_terms:
        #
        # 1.2 Node objects representing the
        #     individual members of the query set.
        #
        #   "HP:0002104": {
        #       "name": "Apnea (HPO)",
        #       "categories": ["biolink:PhenotypicFeature"],
        #       "is_set": False,
        #       "provided_by": ["infores:user-interface"]
        #   }
        #   ...other nodes, one per query_term input
        #
        node_map[term_id] = {
            "id": term_id,
            # TODO: we may not have the name of the term here(?)
            #       unless it is provided in the QGraph?
            # "name": "<some_name>",
            "categories": get_categories(category=query_term_category),
            "is_set": False,
            "provided_by": ["infores:user-interface"]
        }

        #
        # 2.1  Add `member_of` edges that connect the
        #      set node to each of its member CURIEs.
        #
        #     "e0001": {
        #         "subject": "HP:0002104",
        #         "predicate": "biolink:member_of",
        #         "object": "UUID:4403ddf2-f724-4b3b-a877-de08315b784f",
        #         "sources": [
        #             {
        #                 "resource_id": "infores:user-interface",
        #                 "resource_role": "primary_knowledge_source"
        #             }
        #         ],
        #         "attributes": [
        #             {
        #                 "attribute_type_id": "biolink:agent_type",
        #                 "value": "manual_agent",
        #             },
        #             {
        #                 "attribute_type_id": "biolink:knowledge_level",
        #                 "value": "knowledge_assertion",
        #             }
        #         ]
        #     }
        #     ...other 'member_of' edges, one per input query term
        #
        member_edge_id: str = next_edge_id()
        trapi_response["knowledge_graph"]["edges"][member_edge_id] = {
            "subject": term_id,
            "predicate": "biolink:member_of",
            "object": input_query_set_id,
            "sources": [
                {
                    "resource_id": "infores:user-interface",
                    "resource_role": "primary_knowledge_source"
                }
            ],
            "attributes": [
                {
                    "attribute_type_id": "biolink:agent_type",
                    "value": "manual_agent",
                },
                {
                    "attribute_type_id": "biolink:knowledge_level",
                    "value": "knowledge_assertion",
                }
            ]
        }
        query_term_membership_edges[term_id] = member_edge_id

    result_map: RESULTS_MAP = result["result_map"]
    for matched_term_id, result_entry in result_map.items():

        # TODO: how do we keep tabs of results in order
        #       to distinguish between 'MANY' and 'ALL" results?

        #
        # 1.3 Capture the primary answer node object matched, i.e. identified disease
        #
        #   "MONDO:0008807": {
        #       "name": "obsolete apnea, central sleep",
        #       "categories": ["biolink:Disease"],
        #       "is_set": False,
        #       "provided_by": ["infores:semsimian-kp"]  # or should this be MONDO?
        #   }
        if matched_term_id not in node_map:
            node_map[matched_term_id] = {
                "id": matched_term_id,
                "name": result_entry["name"],
                "categories": get_categories(category=result_entry["category"]),
                "is_set": False,
                "provided_by": result_entry["provided_by"]
            }
        #
        # Creation of 'Answer Edges' that connect result nodes to the queried set node
        #
        # 2.2 MCQ services MUST create Answer Edges that connect CURIEs representing each result
        #     they generate, to the UUID of the queried set, then add them to the knowledge_graph.
        #     These edges should use a predicate that matches what is specified by the query.
        #
        # "answer_edge_1": {
        #     "subject": "MONDO:0008807",
        #     "predicate": "similar_to",
        #     "object": "UUID:4403ddf2-f724-4b3b-a877-de08315b784f",
        #     "sources": [
        #         {
        #            "resource_id": "infores:semsimian-kp",
        #            "resource_role": "primary_knowledge_source",
        #            "source_record_urls": None,
        #            "upstream_resource_ids": ["infores:upheno"]
        #         },
        #         {
        #            "resource_id": "infores:monarchinitiative",
        #            "resource_role": "aggregator_knowledge_source",
        #            "source_record_urls": None,
        #            "upstream_resource_ids": [
        #              "infores:semsimian-kp"
        #            ]
        #         },
        #         {
        #             "resource_id": "infores:upheno",
        #             "resource_role": "supporting_data_source",
        #             "source_record_urls": None,
        #             "upstream_resource_ids": None
        #         }
        #     ]
        #     "attributes": [
        #         {
        #             "attribute_type_id": "biolink:agent_type",
        #             "value": "manual_agent",
        #         },
        #         {
        #             "attribute_type_id": "biolink:knowledge_level",
        #             "value": "knowledge_assertion",
        #         }
        #     ]
        #     "support_graphs": [
        #         "ag1",
        #         "ag2"
        #     ]
        # }

        # RESULT_MAPS-level answer 'score'.
        # Unsure whether to put it on the answer edge below since
        # the match to query terms may be indirect and
        # sometimes, matching only a subset of the terms?
        answer_score = result_entry["score"]

        # Complete the shared 'sources' edge provenance block
        answer_sources: List[Dict] = deepcopy(common_sources)
        if "provided_by" in result_entry:
            answer_sources.append(
                {
                    "resource_id": result_entry["provided_by"],
                    "resource_role": "supporting_data_source"
                }
            )

        # Add the 'e002' 'answer edge', as described above,
        # directly reporting that the (UUID-identified) input term
        # subset is similar (phenotypically) to a particular Disease

        # Generate the local TRAPI Response identifiers associated with
        # the 'e001' core similarity 'answer' edge mapping the
        # (UUID-identified) multi-curie subset of query (HPO) input terms,
        # onto the term profile matched node (e.g. MONDO "disease")
        answer_edge_id: str = next_edge_id()
        support_graph_id: str = f"sg-{answer_edge_id}"
        trapi_response["auxiliary_graphs"][support_graph_id] = {"edges": []}

        # Build the core similarity 'answer' edge:
        # "Disease--[similar_to]->Query_Phenotype_Set"
        trapi_response["knowledge_graph"]["edges"][answer_edge_id] = {
            "subject": matched_term_id,
            "predicate": "biolink:similar_to",
            "object": input_query_set_id,
            "sources": deepcopy(answer_sources),
            "attributes": [
                {
                    "attribute_type_id": "biolink:score",
                    "original_attribute_name": AGGREGATE_SIMILARITY_SCORE,
                    "value": answer_score,
                    "value_type_id": "linkml:Float",
                    "attribute_source": primary_knowledge_source
                },
                {
                    "attribute_type_id": "biolink:support_graphs",
                    "value": [support_graph_id],
                    "value_type_id": "linkml:String",
                    "attribute_source": primary_knowledge_source
                },
                {
                    "attribute_type_id": "biolink:agent_type",
                    "value": "automated_agent",
                },
                {
                    "attribute_type_id": "biolink:knowledge_level",
                    "value": "knowledge_assertion",
                }
            ]
        }

        # Extract the various terms matched by the query
        matches: MATCH_LIST = result_entry["matches"]
        term_data: TERM_DATA

        # Note that the term_data entries here report
        # SemSimian "similarity.object_best_matches"
        for term_data in matches:

            term_subject_id: str = term_data["subject_id"]
            term_object_id: str = term_data["object_id"]

            # Add subject and object terms uniquely to nodes catalog, if not already present
            # The identical Biolink concept 'category' is assumed for both nodes
            if term_subject_id not in node_map:
                node_map[term_subject_id] = {
                    "id": term_subject_id,
                    "name": term_data["subject_name"],
                    "categories": get_categories(category=term_data["category"])
                }
            if "name" not in node_map[term_subject_id]:
                node_map[term_subject_id]["name"] = term_data["subject_name"]

            if term_object_id not in node_map:
                node_map[term_object_id] = {
                    "id": term_object_id,
                    "name": term_data["object_name"],
                    "categories": get_categories(category=term_data["category"])
                }
            if "name" not in node_map[term_object_id]:
                node_map[term_object_id]["name"] = term_data["object_name"]

            # Add "support graph" edges to the "knowledge_graph"

            # "Match_Associated_Term--[similar_to]->Input_Query_Term"
            #
            # A support graph edge reporting one of many pairwise similarity assertions between
            # a phenotype associated with a returned Matched term (e.g. Disease)
            # and an input query term (e.g. input phenotype of interest).
            #
            match_to_input_term_edge_id: str = next_edge_id()
            trapi_response["knowledge_graph"]["edges"][match_to_input_term_edge_id] = {
                "subject": term_subject_id,
                "predicate": "biolink:similar_to",
                "object": term_object_id,
                "sources": deepcopy(answer_sources),
                "attributes": [
                    {
                        "attribute_type_id": "biolink:score",
                        "original_attribute_name": MATCH_TERM_SCORE,
                        "value": term_data["score"],
                        "value_type_id": "linkml:Float",
                        "attribute_source": primary_knowledge_source
                    },
                    {
                        "attribute_type_id": "biolink:match",
                        "original_attribute_name": MATCH_TERM,
                        # this is the common subsumer i.e. 'matched_term'
                        "value": term_data["matched_term"],
                        "value_type_id": "linkml:Uriorcurie",
                        "attribute_source": primary_knowledge_source
                    },
                    {
                        "attribute_type_id": "biolink:agent_type",
                        "value": "automated_agent",
                    },
                    {
                        "attribute_type_id": "biolink:knowledge_level",
                        "value": "knowledge_assertion",
                    }
                ]
            }
            trapi_response["auxiliary_graphs"][support_graph_id]["edges"].append(match_to_input_term_edge_id)

            #  "Matched_Term--[<match_predicate>]->Associated_Term"
            #
            #  A support graph edge reporting the associated term (e.g. Phenotype) in the
            #  pairwise-similarity edge associated with the matched term (e.g. Disease) result.

            matched_term_edge_id: str = next_edge_id()
            trapi_response["knowledge_graph"]["edges"][matched_term_edge_id] = {
                "subject": matched_term_id,
                "predicate": match_predicate,
                "object": term_subject_id,
                "sources": [
                    {
                        "resource_id": ingest_knowledge_source,
                        "resource_role": "primary_knowledge_source"
                    }
                ],
                "attributes": [
                    {
                        "attribute_type_id": "biolink:has_evidence",
                        "value": "ECO:0000304",
                        # ECO code for 'author statement supported by
                        # traceable reference used in manual assertion'
                        "value_type_id": "linkml:Uriorcurie",
                        "attribute_source": ingest_knowledge_source
                    },
                    # TODO: the following attribute needs to be the
                    #       HPO Annotations publication, whose value
                    #       is retrieved from the Monarch (e.g. HPOA ingest),
                    #       linking the phenotype with its disease.
                    # {
                    #     "attribute_type_id": "biolink:publications",
                    #     "value": ["orphanet:137935"],
                    #     "value_type_id": "linkml:Uriorcurie",
                    #     "attribute_source": ingest_knowledge_source
                    # }
                    {
                        "attribute_type_id": "biolink:agent_type",
                        "value": "automated_agent",
                    },
                    {
                        "attribute_type_id": "biolink:knowledge_level",
                        "value": "knowledge_assertion",
                    }
                ]
            }
            trapi_response["auxiliary_graphs"][support_graph_id]["edges"].append(matched_term_edge_id)

            # All match results are linked to the input query terms matched,
            # so add the set membership edges to the corresponding support graph
            trapi_response["auxiliary_graphs"][support_graph_id]["edges"]\
                .append(query_term_membership_edges[term_object_id])

        # "results" list entry for the current "object_id" similarity match
        trapi_results_entry: Dict = {
            "node_bindings": {
                qnode_subject_key: [{"id": input_query_set_id}],
                qnode_object_key: [{"id": matched_term_id}]
            },
            "analyses": [
                {
                    "resource_id": provenance,
                    "edge_bindings": {"e01": [{"id": answer_edge_id}]}
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
