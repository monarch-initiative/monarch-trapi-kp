"""
TRAPI JSON accessing data utilities.
This module knows about the TRAPI syntax such that it can
extract parameters and build TRAPI Responses from results
"""
from typing import Optional, Any, List, Dict
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


def mcq_subject_qnode(node_data: Dict) -> Optional[str]:
    """
    Checks if the query node is the node holding the query terms
    and returns the associated categories of that node, as a 'True'
    boolean testable value; None otherwise.
    :param node_data: QNode details for a single node.
    :raises: RuntimeError if the query node is not a well-formed
             multi-curie query input set specification.
    """
    if "is_set" in node_data and node_data["is_set"] and \
            "set_interpretation" in node_data and node_data["set_interpretation"] and \
            node_data["set_interpretation"] in ["MANY", "ALL"]:
        if "ids" in node_data and len(node_data["ids"]) == 1 and \
                str(node_data["ids"][0]).upper().startswith("UUID:") and \
                "member_ids" in node_data and len(node_data["member_ids"]) > 0:
            # Success: well-formed node of 'set_interpretation' type 'MANY' or 'ALL'!
            # TODO: fix this to grab the most specific category
            #       from the list in case there are several?
            return node_data["categories"][0]
        else:
            # Failure: not well-formed
            raise RuntimeError(
                "Query Graph Node 'set_interpretation' is 'MANY' or 'ALL', thus 'ids' "
                "must have a single global ('UUID') set identifier and query input identifiers "
                "for the set need to be listed in the 'member_ids' list."
            )
    else:
        # Not a set of 'set_interpretation' type 'MANY' or 'ALL'
        return None


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

        ("MONDO:0008807":"biolink:Disease")
            --["biolink:similar_to"]->
            ("UUID:c5d67629-ce16-41e9-8b35-e4acee04ed1f":"biolink:PhenotypicFeature")

    where "UUID:c5d67629-ce16-41e9-8b35-e4acee04ed1f" designates the set
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
    assert trapi_message, "build_trapi_message(): Empty TRAPI Message?"

    # Code to extract (meta-)data from the TRAPI Request Message Query Graph
    nodes: Dict = trapi_message["query_graph"]["nodes"]
    qnode_id: str
    node_data: Dict
    qnode_subject_key: str = "n0"
    qnode_object_key: str = "n1"

    if not nodes or len(nodes) > 2:
        return {"error": f"build_trapi_message(): exact two query nodes are required; saw: '{str(nodes)}'?"}

    for qnode_id, node_data in nodes.items():
        try:
            if mcq_subject_qnode(node_data):
                qnode_subject_key = qnode_id
            else:
                qnode_object_key = qnode_id
        except RuntimeError as rte:
            return {"error": str(rte)}

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

    # TODO: we need to filter output somewhere below based upon
    #       'MANY' versus 'ALL' values of set_interpretation
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

    primary_answer_term_id: str
    node_map: Dict = dict()
    reset_edge_idx()
    query_term_membership_edges: Dict[str, str] = dict()

    ##################################################################################
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
            #       unless it is provided in the QGraph, but it
            #       could be harvested from the SemSimian results (below)
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
    for primary_answer_term_id, result_entry in result_map.items():

        # Complete the shared 'sources' edge provenance block
        answer_sources: List[Dict] = deepcopy(common_sources)
        if "provided_by" in result_entry:
            answer_sources.append(
                {
                    "resource_id": result_entry["provided_by"],
                    "resource_role": "supporting_data_source"
                }
            )

        # Extract the various terms matched by the query
        matches: MATCH_LIST = result_entry["matches"]
        term_data: TERM_DATA

        # Tracking observed matches for completeness relating
        # to 'MANY' versus 'ALL' set interpretation
        input_query_term_seen: Dict[str, bool] = {term: False for term in query_terms}

        # Cache query term matches to defer their addition to the response
        # pending the 'MANY' versus 'ALL' set interpretation expectations
        query_term_match_cache: Dict[str, Dict[str, Any]] = dict()

        # Note that the term_data entries here report
        # SemSimian "similarity.object_best_matches"
        for term_data in matches:

            term_subject_id: str = term_data["subject_id"]  # SemSimian matched term
            term_object_id: str = term_data["object_id"]    # matching input query term

            if term_subject_id in query_term_match_cache:
                # TODO: is matching a subject term id twice could
                #       be considered a SemSemian bug or odd limitation?
                #       Perhaps compare match scores and only keep
                #       the query term matching with higher score
                if term_data["score"] < query_term_match_cache[term_subject_id]["score"]:
                    # ignoring lower scoring query term matches
                    continue
                else:
                    # ignoring the previous observed lower scoring query term
                    input_query_term_seen[query_term_match_cache[term_subject_id]["query_term"]] = False
                    # Overwriting matched_term_cache[term_subject_id] with new data below...
            else:
                query_term_match_cache[term_subject_id] = dict()

            # Track input term matches, for 'MANY' version 'ALL'
            # 'set_expectation' driven result filtering later
            if term_object_id in input_query_term_seen:
                input_query_term_seen[term_object_id] = True

            # Cache the core subject match node details
            query_term_match_cache[term_subject_id]["name"] = term_data["subject_name"]
            query_term_match_cache[term_subject_id]["category"] = term_data["category"]
            query_term_match_cache[term_subject_id]["query_term"] = term_object_id
            query_term_match_cache[term_subject_id]["score"] = term_data["score"]
            query_term_match_cache[term_subject_id]["primary_answer_term"] = primary_answer_term_id

            #
            # TODO: this seems to be duplicate code the 'term_object_id'
            #       already recorded in the node_map above?
            #
            # if term_object_id not in node_map:
            #     node_map[term_object_id] = {
            #         "id": term_object_id,
            #         "name": term_data["object_name"],
            #         "categories": get_categories(category=term_data["category"])
            #     }
            # TODO: ...however, here, maybe we can (and need to) capture the
            #       query term which was not previously conveniently available?
            if "name" not in node_map[term_object_id]:
                node_map[term_object_id]["name"] = term_data["object_name"]

            # Cache the "support graph" edges to be added
            # to the "knowledge_graph", if and when specific
            # 'set_interpretation' expectations are met (see below)
            query_term_match_cache[term_subject_id]["edges"] = dict()

            #
            # "Match_Associated_Term--[similar_to]->Input_Query_Term"
            #
            # "match_to_input_term_edge_id": {
            #     "subject": "HP:0001699",
            #     "predicate": "similar_to",
            #     "object": "HP:0012378",
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
            #             "resource_id": "infores:hpo-annotations",
            #             "resource_role": "supporting_data_source",
            #             "source_record_urls": None,
            #             "upstream_resource_ids": None
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
            #             "attribute_type_id": "biolink:score",
            #             "original_attribute_name": 15.021529465404182,
            #             "value": term_data["score"],
            #             "value_type_id": "linkml:Float",
            #             "attribute_source": primary_knowledge_source
            #         },
            #         {
            #             "attribute_type_id": "biolink:match",
            #             "original_attribute_name": "HP:0025142",
            #             # this is the common subsumer i.e. 'matched_term'
            #             "value": term_data["matched_term"],
            #             "value_type_id": "linkml:Uriorcurie",
            #             "attribute_source": primary_knowledge_source
            #         },
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
            #         "match_edge_support_graph"
            #     ]
            # }
            # A support graph edge reporting one of many pairwise similarity assertions between
            # a phenotype associated with a returned Matched term (e.g. Disease)
            # and an input query term (e.g. input phenotype of interest).
            #
            match_to_input_term_edge_id: str = next_edge_id()
            query_term_match_cache[term_subject_id]["edges"][match_to_input_term_edge_id] = {
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

            #
            #  "Matched_Term--[<match_predicate>]->Associated_Term"
            #
            # "matched_term_edge_id": {
            #     "subject": "HP:0001699",
            #     "predicate": "similar_to",
            #     "object": "HP:0012378",
            #     "sources": [
            #         {
            #             "resource_id": "infores:hpo-annotations",
            #             "resource_role": "primary_knowledge_source",
            #             "source_record_urls": None,
            #             "upstream_resource_ids": None
            #         },
            #         {
            #            "resource_id": "infores:monarchinitiative",
            #            "resource_role": "aggregator_knowledge_source",
            #            "source_record_urls": None,
            #            "upstream_resource_ids": [
            #               "infores:hpo-annotations"
            #            ]
            #         }
            #     ]
            #     "attributes": [
            #         {
            #             "attribute_type_id": "biolink:has_evidence",
            #             "value": "ECO:0000304",
            #             # ECO code for 'author statement supported by
            #             # traceable reference used in manual assertion'
            #             "value_type_id": "linkml:Uriorcurie",
            #             "attribute_source": "infores:hpo-annotations"
            #         },
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
            #         "match_edge_support_graph"
            #     ]
            # }
            #
            #  A support graph edge reporting the matched term (e.g. Disease) in the
            #  pairwise-similarity edge associated with the associated term (e.g. Phenotype) result.

            matched_term_edge_id: str = next_edge_id()
            query_term_match_cache[term_subject_id]["edges"][matched_term_edge_id] = {
                "subject": primary_answer_term_id,
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

        if set_interpretation == 'ALL' and not all(input_query_term_seen.values()):
            # Skip this term_data result since the 'set_interpretation' of 'ALL'
            # strictly expects that all the input query terms are matched by SemSemian
            continue

        # else: a 'MANY' expectation is more lenient, therefore,
        #       any and all (possibly partial) matches are passed on

        # If we get past the 'set_interpretation', then it is now safe
        # to add the current new term_data cache matches to the TRAPI Response

        #
        # 1.3 Add the primary answer node object matched,
        #     i.e. identified disease - to the TRAPI Response nodes list
        #
        #   "MONDO:0008807": {
        #       "name": "obsolete apnea, central sleep",
        #       "categories": ["biolink:Disease"],
        #       "is_set": False,
        #       "provided_by": ["infores:semsimian-kp"]  # or should this be MONDO?
        #   }
        if primary_answer_term_id not in node_map:
            node_map[primary_answer_term_id] = {
                "id": primary_answer_term_id,
                "name": result_entry["name"],
                "categories": get_categories(category=result_entry["category"]),
                "is_set": False,
                "provided_by": result_entry["provided_by"]
            }

        #
        # 2.2 MCQ services MUST create Answer Edges that connect CURIEs representing each result
        #     they generate, to the UUID of the queried set, then add them to the knowledge_graph.
        #     These edges should use a predicate that matches what is specified by the query.
        # Build the core similarity 'answer' edge:
        # "Disease--[similar_to]->Query_Phenotype_Set"
        #
        # "answer_edge_id": {
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
        #             "resource_id": "infores:hpo-annotations",
        #             "resource_role": "supporting_data_source",
        #             "source_record_urls": None,
        #             "upstream_resource_ids": None
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
        #             "attribute_type_id": "biolink:score",
        #             "original_attribute_name": AGGREGATE_SIMILARITY_SCORE,
        #             "value": answer_score,
        #             "value_type_id": "linkml:Float",
        #             "attribute_source": primary_knowledge_source
        #         },
        #         {
        #             "attribute_type_id": "biolink:support_graphs",
        #             "value": [support_graph_id],
        #             "value_type_id": "linkml:String",
        #             "attribute_source": primary_knowledge_source
        #         },
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
        #         "sg1",
        #         etc...
        #     ]
        # }
        # Generate the local TRAPI Response identifiers associated with
        # the core knowledge graph similarity 'answer' edge mapping
        # the term profile matched node (e.g. MONDO "disease") onto
        # (UUID-identified) multi-curie subset of query (HPO) input terms,
        answer_edge_id: str = next_edge_id()

        # Capture potential auxiliary 'support' graph along the way...
        support_graph_id: str = f"sg-{answer_edge_id}"

        answer_score = result_entry["score"]
        trapi_response["knowledge_graph"]["edges"][answer_edge_id] = {
            "subject": primary_answer_term_id,
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

        # Expect some answer edge specific support graphs
        trapi_response["auxiliary_graphs"][support_graph_id] = {"edges": []}

        term_match_id: str
        details: Dict
        for term_match_id, details in query_term_match_cache.items():
            if term_match_id not in node_map:
                node_map[term_match_id] = {
                    "id": term_match_id,
                    "name": details["name"],
                    "categories": get_categories(category=details["category"])
                }

            edge_id: str
            edge_details: Dict
            for edge_id, edge_details in details["edges"].items():
                trapi_response["knowledge_graph"]["edges"][edge_id] = edge_details
                trapi_response["auxiliary_graphs"][support_graph_id]["edges"].append(edge_id)

            # All match results are linked to the input query terms matched,
            # so add the query term's 'set membership' edge to the support graph
            trapi_response["auxiliary_graphs"][support_graph_id]["edges"]\
                .append(query_term_membership_edges[details["query_term"]])

        # Record the 'core' answer relationship to TRAPI Response "Results"
        trapi_results_entry: Dict = {
            "node_bindings": {
                qnode_subject_key: [{"id": input_query_set_id}],
                qnode_object_key: [{"id": primary_answer_term_id}]
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
