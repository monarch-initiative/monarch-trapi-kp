"""
GraphAdapter to Monarch graph API
"""
from typing import List, Dict
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
        async def semsim_search(
                identifiers: List[str],
                group: SemsimSearchCategory
        ) -> Dict[str, List[str]]:
            """
            Generalized call to Monarch SemSim search endpoint.
            :param identifiers: list of identifiers to be matched.
            :param group: concept category targeted for matching.
            :return:
            """
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

        async def phenotype_semsim_to_disease(self, phenotype_ids: List[str]) -> Dict[str, List[str]]:
            """
            :param phenotype_ids: list of (HPO?) phenotype identifiers
            :type phenotype_ids: List[str]
            :return: Dictionary indexed by (MONDO) disease CURIEs
                     against lists of matching phenotype feature CURIEs
            :rtype: Dict[str, List[str]]
            """
            result: Dict[str, List[str]] = await self.semsim_search(
                identifiers=phenotype_ids, group=SemsimSearchCategory.HGNC
            )
            return result

        async def run_query(self, identifiers: List[str]) -> Dict[str, List[str]]:
            """
            Simple highly specialized query MVP use case against Monarch (eventually needs to be generalized):
                 Sends a list of phenotype (HP ontology term) CURIEs to a
                 Semantic Similarity search of the Monarch API for matching diseases.
                 No scoring metrics are returned (yet) from semsimian in this iteration.

            :param identifiers: Python dictionary version of query parameters
            :type identifiers: Dict
            :return: Dictionary of Monarch 'object' identifier hits indexing Lists of matched 'subject' identifiers.
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
