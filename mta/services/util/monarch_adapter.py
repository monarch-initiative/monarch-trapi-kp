"""
GraphAdapter to Monarch graph API
"""
from typing import Optional, Any, List, Dict
from enum import Enum
import requests

# from bmt import Toolkit

from mta.services.config import config
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


def get_nested_tag_value(data: Dict, path: List[str], pos: int) -> Optional[Any]:
    """
    Navigate dot delimited tag 'path' into a multi-level dictionary, to return its associated value.

    :param data: Dict, multi-level data dictionary
    :param path: str, dotted JSON tag path
    :param pos: int, zero-based current position in tag path
    :return: string value of the multi-level tag, if available; 'None' otherwise if no tag value found in the path
    """
    tag = path[pos]
    part_tag_path = ".".join(path[:pos+1])
    if tag not in data:
        logger.debug(f"\tMissing tag path '{part_tag_path}'?")
        return None

    pos += 1
    if pos == len(path):
        return data[tag]
    else:
        return get_nested_tag_value(data[tag], path, pos)


def tag_value(json_data, tag_path) -> Optional[Any]:
    """
    Retrieve value of leaf in multi-level dictionary at
    the end of a specified dot delimited sequence of keys.
    :param json_data:
    :param tag_path:
    :return:
    """
    if not tag_path:
        logger.debug(f"\tEmpty 'tag_path' argument?")
        return None

    parts = tag_path.split(".")
    return get_nested_tag_value(json_data, parts, 0)


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

        # TODO: add useful _GraphInterface methods here!
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
                group: SemsimSearchCategory
        ) -> List[Dict]:
            """
            Generalized call to Monarch SemSim search endpoint.
            :param identifiers: list of identifiers to be matched.
            :param group: concept category targeted for matching.
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
            #   "termset": ["HP:0002104", "HP:0012378", "HP:0012378", "HP:0012378"],
            #   "group": "Human Diseases",
            #   "limit": 5
            # }'
            #
            query = {
              "termset": identifiers,
              "group": group.value,
              "limit": 5
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
                logger.error(
                    f"Monarch SemSimian at '\nUrl: '{MONARCH_SEMSIMIAN}', "
                    f"Query: '{query}' returned HTTP error code: '{response.status_code}'"
                )
                return list()

            return response.json()

        @staticmethod
        def parse_raw_semsim(full_result: List[Dict]) -> Dict[str, List[str]]:
            """
            Parse out the SemSimian matched objects associated with specified subject ids.
            :param full_result: raw Semsimian result
            :type full_result: List[SemsimSearchResult]
            :return: Dict[str, List[str]], results indexed by matched subjects
                     with similarity profiles matching query inputs
            """
            result: Dict[str, List[str]] = dict()
            for entry in full_result:
                subject_id = tag_value(entry, "subject.id")
                object_termset: Dict = tag_value(entry, "similarity.object_termset")
                if object_termset:
                    result[subject_id] = list(object_termset.keys())
            return result

        async def phenotype_semsim_to_disease(self, phenotype_ids: List[str]) -> Dict[str, List[str]]:
            """
            :param phenotype_ids: list of (HPO?) phenotype identifiers
            :type phenotype_ids: List[str]
            :return: Dictionary indexed by (MONDO) disease CURIEs
                     against lists of matching phenotype feature CURIEs
            :rtype: Dict[str, List[str]]
            """
            full_result: List[Dict] = await self.semsim_search(
                identifiers=phenotype_ids, group=SemsimSearchCategory.MONDO
            )
            result: Dict[str, List[str]] = self.parse_raw_semsim(full_result)
            return result

        async def run_query(self, identifiers: List[str]) -> Dict[str, List[str]]:
            """
            Initial MVP is a single highly specialized query MVP use case against Monarch.
                 Sends an input list of (HPO-indexed) phenotypic feature CURIEs to a
                 Monarch Semantic Similarity search to match (MONDO-indexed) Diseases.
                 No scoring metrics or supporting evidence (yet) returned in this iteration.

            :param identifiers: Python dictionary version of query parameters
            :type identifiers: Dict
            :return: Dictionary of Monarch 'subject' identifier hits indexing Lists of matched input identifiers.
            :rtype: Dict[str, List[str]]
            """
            result: Dict[str, List[str]] = await self.phenotype_semsim_to_disease(phenotype_ids=identifiers)
            return result

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
