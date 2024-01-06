"""
GraphAdapter to Monarch graph API
"""
from typing import Any, List, Dict
from enum import Enum
# from bmt import Toolkit

LATEST_BIOLINK_MODEL = "1.4.0"


class SemsimSearchCategory(Enum):
    HGNC = "Human Genes"
    MGI = "Mouse Genes"
    RGD = "Rat Genes"
    ZFIN = "Zebrafish Genes"
    WB = "C. Elegans Genes"
    MONDO = "Human Diseases"


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
        def get_phenotype_ids(trapi_query: Dict) -> List[str]:
            return list()

        @staticmethod
        async def semsim_search(
                identifiers: List[str],
                group: SemsimSearchCategory = SemsimSearchCategory.HGNC
        ) -> Dict[str, List[str]]:
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
            # Gives a result like:
            #
            #   SemsimSearchResult:
            #     slots:
            #       - subject
            #       - score
            #       - similarity
            #     slot_usage:
            #       subject:
            #         range: Entity
            #         inlined: true

            return dict()

        async def phenotype_semsim_to_disease(self, trapi_query: Dict) -> Dict[str, List[str]]:
            """
            :param trapi_query: Python dictionary version of TRAPI Query JSON
            :type trapi_query: Dict
            :return: Dictionary indexed by (MONDO) disease CURIEs
                     against lists of matching phenotype feature CURIEs
            :rtype: Dict[str, List[str]]
            """
            hp_ids: List[str] = self.get_phenotype_ids(trapi_query)
            result: Dict[str, List[str]] = await self.semsim_search(identifiers=hp_ids)
            return result

        async def run_query(self, parameters: Dict) -> Dict[str, List[str]]:
            """
            Run a query against the Monarch API.
            :param parameters: Python dictionary version of query parameters
            :type parameters: Dict
            :return: Dictionary of Monarch hits along with List of matched input identifiers.
            :rtype: Dict[str, List[str]]
            """
            parameters['timeout'] = self.query_timeout
            # TODO: Implement me!
            result: Dict[str, List[str]] = dict()
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
