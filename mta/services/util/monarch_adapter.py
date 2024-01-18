"""
GraphAdapter to Monarch graph API
"""
from typing import Optional, List, Dict
from enum import Enum
import requests

from mta.services.config import config
from mta.services.util import (
    TERM_DATA,
    MATCH_LIST,
    RESULT_ENTRY,
    RESULTS_MAP,
    RESULT,
    tag_value
)
from mta.services.util.logutil import LoggingUtil

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

LATEST_BIOLINK_MODEL = "1.4.0"
MONARCH_SEMSIMIAN = "http://api-v3.monarchinitiative.org/v3/api/semsim/search"


class SemsimSearchCategory(Enum):
    HGNC = "Human Genes"
    MGI = "Mouse Genes"
    RGD = "Rat Genes"
    ZFIN = "Zebrafish Genes"
    WB = "C. Elegans Genes"
    MONDO = "Human Diseases"


_map_source: Dict = {
    "phenio_nodes": "infores:upheno"
}


class MonarchInterface:
    """
    Singleton class for interfacing with the Monarch Initiative graph.
    """
    class _MonarchInterface:
        def __init__(self, query_timeout, bl_version=LATEST_BIOLINK_MODEL):
            self.schema = None
            # used to keep track of derived inverted predicates
            # self.inverted_predicates = defaultdict(lambda: defaultdict(set))
            self.query_timeout = query_timeout
            # self.toolkit = Toolkit()
            self.bl_version = bl_version

        async def get_node(
                self,
                node_type: str,
                curie: str
        ) -> Dict:
            """
            Returns a node that matches curie as its ID.
            :param node_type: Type of the node.
            :type node_type:str
            :param curie: Curie.
            :type curie: str
            :return: Contents of the node in Monarch.
            :rtype: Dict
            """
            # TODO: Implement me!
            return dict()

        async def get_single_hops(self, source_type: str, target_type: str, curie: str) -> List:
            """
            Returns a triplets of source to target where source id is curie.
            :param source_type: Type of the source node.
            :type source_type: str
            :param target_type: Type of target node.
            :type target_type: str
            :param curie: Curie of source node.
            :type curie: str
            :return: List of triplets where each item contains source node, edge, target.
            :rtype: List
            """
            # TODO: Implement me!
            return list()

        @staticmethod
        async def semsim_search(
                identifiers: List[str],
                group: SemsimSearchCategory,
                result_limit: int
        ) -> List[Dict]:
            """
            Generalized call to Monarch SemSim search endpoint.
            :param identifiers: List[str], list of identifiers to be matched.
            :param group: SemsimSearchCategory, concept category targeted for matching.
            :param result_limit: int, the limit on the number of query results to be returned.
            :return: List[Dict], of 'raw' SemSimian result objects
            """
            #
            # Example HTTP POST to SemSimian:
            #
            # curl -X 'POST' \
            #   'http://api-v3.monarchinitiative.org/v3/api/semsim/search' \
            #   -H 'accept: application/json' \
            #   -H 'Content-Type: application/json' \
            #   -d '{
            #   "termset": ["HP:0002104", "HP:0012378"],
            #   "group": "Human Diseases",
            #   "limit": 5
            # }'
            #
            query = {
              "termset": identifiers,
              "group": group.value,
              "limit": result_limit
            }
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json"
            }
            response = requests.post(
                MONARCH_SEMSIMIAN,
                json=query,
                headers=headers
            )

            if not response.status_code == 200:
                error_msg = f"Monarch SemSimian at '\nUrl: '{MONARCH_SEMSIMIAN}', Query: '{query}' returned HTTP error code: '{response.status_code}'"
                logger.error(error_msg)
                error: Dict = {"error": error_msg}
                return [error]

            return response.json()

        @staticmethod
        def parse_raw_semsim(
                full_result: List[Dict],
                match_category: str
        ) -> RESULTS_MAP:
            """
            Parse out the SemSimian matched object terms associated with specified subject ids.
            :param full_result: List[SemsimSearchResult], raw Semsimian result
            :param match_category: str, Biolink Model concept category of matched terms (not provided by SemSimian?)
            :return: RESULT_MAP, results indexed by matched subjects,
                                 with similarity profiles matching query inputs
            """
            result: RESULTS_MAP = dict()
            for entry in full_result:
                # Subtle reversion of assertion: SemSimian
                # 'subject' becomes the 'object' of interest
                object_id = tag_value(entry, "subject.id")
                result[object_id]: RESULT_ENTRY = dict()
                subject_name = tag_value(entry, "subject.name")
                result[object_id]["name"] = subject_name
                subject_category = tag_value(entry, "subject.category")
                result[object_id]["category"] = subject_category
                result[object_id]["score"] = entry["score"]

                provided_by = tag_value(entry, "subject.provided_by")
                if provided_by:
                    result[object_id]["provided_by"] = \
                        _map_source.setdefault(provided_by, f"infores:{provided_by}")

                # We only take the Similarity 'object_best_matches'
                # for which the 'match_source' values correspond
                # to the original input query terms
                object_best_matches: Dict = tag_value(entry, f"similarity.object_best_matches")
                result[object_id]["matches"]: MATCH_LIST = list()
                if object_best_matches:
                    for object_match in object_best_matches.values():
                        similarity: Dict = object_match["similarity"]
                        matched_term: str = similarity["ancestor_id"] \
                            if similarity["ancestor_id"] else object_match["match_target"]
                        term_data: TERM_DATA = {
                            "subject_id": object_match["match_source"],
                            "subject_name": object_match["match_source_label"],
                            "category": match_category,
                            "object_id": object_match["match_target"],
                            "object_name": object_match["match_target_label"],
                            "score": object_match["score"],
                            "matched_term": matched_term
                        }
                        result[object_id]["matches"].append(term_data)

            return result

        async def phenotype_semsim_to_disease(self, trapi_message: Dict, result_limit: int) -> RESULT:
            """
            Initial MVP is a single somewhat hardcoded MVP query against Monarch,
            sending an input list of (HPO-indexed) phenotypic feature CURIEs
            to a Monarch SemSimian search to match (MONDO-indexed) Diseases.

            TODO: this query can probably be generalized at this level since likely both
                  the semsim_search 'group' and result 'ingest_knowledge_source' can be
                  parameterized given proper interpretation of the input TRAPI message.

            :param trapi_message: Dict, TRAPI Request.Message.QueryGraph query data.
            :param result_limit: int, the limit on the number of query results to be returned.
            :return: RESULT dictionary of metadata and a RESULT_MAP, indexed by target curies,
                    containing the target annotation, plus lists of annotated RESULT_ENTRY
                    instances of similarity matching phenotypic feature terms.
            :rtype: RESULT
            """
            nodes: Dict = trapi_message["query_graph"]["nodes"]
            qnode_id: str
            details: Dict
            query_terms: Optional[List[str]] = None
            category: Optional[str] = None
            for qnode_id, details in nodes.items():
                # Gatekeeper signal "is_set" and "set_interpretation"
                # with "ids" - these are the input terms?
                if "is_set" in details and details["is_set"] and \
                        "set_interpretation" in details and details["set_interpretation"] == "OR+" and \
                        "ids" in details:
                    query_terms = details["ids"]

                    # blind assumption: associated terms 'category' is properly set here in this query
                    category = details["categories"][0] \
                        if "categories" in details and details["categories"] else "biolink:NamedThing"

            result: RESULT = dict()

            if query_terms is not None:
                full_result: List[Dict] = await self.semsim_search(
                    identifiers=query_terms,
                    group=SemsimSearchCategory.MONDO,
                    result_limit=result_limit
                )
                if "error" not in full_result[0]:
                    result_map: RESULTS_MAP = self.parse_raw_semsim(
                        full_result=full_result,
                        match_category=category
                    )

                    result["primary_knowledge_source"] = "infores:semsimian-kp"
                    result["ingest_knowledge_source"] = "infores:hpo-annotations"
                    result["match_predicate"] = "biolink:phenotype_of"
                    result["result_map"] = result_map
                else:
                    result["error"] = full_result[0]["error"]

            # may be None if there were no identifiers
            return result

        async def run_query(self, trapi_message: Dict, result_limit: int) -> RESULT:
            """
            Running a SemSim query against Monarch.
            This MVP only supports one (hard-coded) use case. Future versions of this
            method should check the trapi_message for information about the query nature.

            :param trapi_message: Dict, Python dictionary version of query parameters
            :param result_limit: int, the limit on the number of query results to be returned.
            :return: Dictionary of Monarch 'subject' identifier hits indexing
                     Lists of matched input identifiers.
            :rtype: RESULT
            """
            return await self.phenotype_semsim_to_disease(
                trapi_message=trapi_message, result_limit=result_limit
            )

    instance = None

    def __init__(self, query_timeout=600, bl_version=LATEST_BIOLINK_MODEL):
        # create a new instance if not already created.
        if not MonarchInterface.instance:
            MonarchInterface.instance = MonarchInterface._MonarchInterface(
                query_timeout=query_timeout,
                bl_version=bl_version
            )

    def __getattr__(self, item):
        # proxy function calls to the inner object.
        return getattr(self.instance, item)
