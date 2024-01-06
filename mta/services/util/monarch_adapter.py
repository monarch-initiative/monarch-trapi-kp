"""
GraphAdapter to Monarch graph API
"""
from typing import List, Dict
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
            :param full_result: raw Semsimian result
            :type full_result: List[SemsimSearchResult]
            :return: Dict[str, List[str]], results indexed by matched subjects
                     with similarity profiles matching query inputs
            """
            #   SemsimSearchResult: Dict
            #     slots:
            #       - subject
            #       - score
            #       - similarity
            #     slot_usage:
            #       subject:
            #         range: Entity  # has lots of metadata
            #         inlined: true
            #
            # For example:
            #
            # {
            #     'subject': {
            #         'id': 'HGNC:5973',
            #         'category': 'biolink:Gene',
            #         'name': 'IL13',
            #         'full_name': 'interleukin 13',
            #         'deprecated': None,
            #         'description': None,
            #         'xref': ['ENSEMBL:ENSG00000169194', 'OMIM:147683'],
            #         'provided_by': 'hgnc_gene_nodes',
            #         'in_taxon': 'NCBITaxon:9606',
            #         'in_taxon_label': 'Homo sapiens',
            #         'symbol': 'IL13',
            #         'synonym': [
            #             'P600', 'IL-13', 'ALRH', 'BHR1', 'MGC116786', 'MGC116788',
            #             'MGC116789', 'allergic rhinitis', 'Bronchial hyperresponsiveness-1 (bronchial asthma)'
            #         ],
            #         'uri': 'http://identifiers.org/hgnc/5973'
            #     },
            #     'score': 6.704627500804806,
            #     'similarity': {
            #         'subject_termset': {
            #             'HP:0032933': {
            #                 'id': 'HP:0032933',
            #                 'label': 'Airway hyperresponsiveness (HPO)'
            #             },
            #             'HP:4000007': {
            #                 'id': 'HP:4000007',
            #                 'label': 'Bronchoconstriction (HPO)'
            #             },
            #             'HP:0001426': {
            #                 'id': 'HP:0001426',
            #                 'label': 'Multifactorial inheritance (HPO)'
            #             },
            #             'HP:0000006': {
            #                 'id': 'HP:0000006',
            #                 'label': 'Autosomal dominant inheritance (HPO)'
            #             },
            #             'HP:0002099': {
            #                 'id': 'HP:0002099',
            #                 'label': 'Asthma (HPO)'
            #             }
            #         },
            #         'object_termset': {
            #             'HP:0002104': {
            #                 'id': 'HP:0002104',
            #                 'label': 'Apnea (HPO)'
            #             },
            #             'HP:0012378': {
            #                 'id': 'HP:0012378',
            #                 'label': 'Fatigue (HPO)'
            #             }
            #         },
            #         'subject_best_matches': {
            #             'HP:0000006': {
            #                 'match_source': 'HP:0000006',
            #                 'match_source_label': 'Autosomal dominant inheritance (HPO)',
            #                 'match_target': 'HP:0012378',
            #                 'match_target_label': 'Fatigue (HPO)',
            #                 'score': 4.03656792399593,
            #                 'match_subsumer': None,
            #                 'match_subsumer_label': None,
            #                 'similarity': {
            #                     'subject_id': 'HP:0000006',
            #                     'subject_label': None,
            #                     'subject_source': None,
            #                     'object_id': 'HP:0012378',
            #                     'object_label': None,
            #                     'object_source': None,
            #                     'ancestor_id': 'HP:0000001',
            #                     'ancestor_label': '',
            #                     'ancestor_source': None,
            #                     'object_information_content': None,
            #                     'subject_information_content': None,
            #                     'ancestor_information_content': 4.03656792399593,
            #                     'jaccard_similarity': 0.06666666666666667,
            #                     'cosine_similarity': None,
            #                     'dice_similarity': None,
            #                     'phenodigm_score': 0.5187528585621436
            #                 }
            #             },
            #             'HP:0001426': {
            #                 'match_source': 'HP:0001426',
            #                 'match_source_label': 'Multifactorial inheritance (HPO)',
            #                 'match_target': 'HP:0012378',
            #                 'match_target_label': 'Fatigue (HPO)',
            #                 'score': 4.03656792399593,
            #                 'match_subsumer': None,
            #                 'match_subsumer_label': None,
            #                 'similarity': {
            #                     'subject_id': 'HP:0001426',
            #                     'subject_label': None,
            #                     'subject_source': None,
            #                     'object_id': 'HP:0012378',
            #                     'object_label': None,
            #                     'object_source': None,
            #                     'ancestor_id': 'HP:0000001',
            #                     'ancestor_label': '',
            #                     'ancestor_source': None,
            #                     'object_information_content': None,
            #                     'subject_information_content': None,
            #                     'ancestor_information_content': 4.03656792399593,
            #                     'jaccard_similarity': 0.07142857142857142,
            #                     'cosine_similarity': None,
            #                     'dice_similarity': None,
            #                     'phenodigm_score': 0.5369602222561961
            #                 }
            #             },
            #             'HP:0002099': {
            #                 'match_source': 'HP:0002099',
            #                 'match_source_label': 'Asthma (HPO)',
            #                 'match_target': 'HP:0002104',
            #                 'match_target_label': 'Apnea (HPO)',
            #                 'score': 8.877204788271372,
            #                 'match_subsumer': None,
            #                 'match_subsumer_label': None,
            #                 'similarity': {
            #                     'subject_id': 'HP:0002099',
            #                     'subject_label': None,
            #                     'subject_source': None,
            #                     'object_id': 'HP:0002104',
            #                     'object_label': None,
            #                     'object_source': None,
            #                     'ancestor_id': 'HP:0002795',
            #                     'ancestor_label': '',
            #                     'ancestor_source': None,
            #                     'object_information_content': None,
            #                     'subject_information_content': None,
            #                     'ancestor_information_content': 8.877204788271372,
            #                     'jaccard_similarity': 0.5,
            #                     'cosine_similarity': None,
            #                     'dice_similarity': None,
            #                     'phenodigm_score': 2.106799087273318
            #                 }
            #             },
            #             'HP:0032933': {
            #                 'match_source': 'HP:0032933',
            #                 'match_source_label': 'Airway hyperresponsiveness (HPO)',
            #                 'match_target': 'HP:0002104',
            #                 'match_target_label': 'Apnea (HPO)',
            #                 'score': 8.877204788271372,
            #                 'match_subsumer': None,
            #                 'match_subsumer_label': None,
            #                 'similarity': {
            #                     'subject_id': 'HP:0032933',
            #                     'subject_label': None,
            #                     'subject_source': None,
            #                     'object_id': 'HP:0002104',
            #                     'object_label': None,
            #                     'object_source': None,
            #                     'ancestor_id': 'HP:0002795',
            #                     'ancestor_label': '',
            #                     'ancestor_source': None,
            #                     'object_information_content': None,
            #                     'subject_information_content': None,
            #                     'ancestor_information_content': 8.877204788271372,
            #                     'jaccard_similarity': 0.782608695652174,
            #                     'cosine_similarity': None,
            #                     'dice_similarity': None,
            #                     'phenodigm_score': 2.6357878633126552
            #                 }
            #             },
            #             'HP:4000007': {
            #                 'match_source': 'HP:4000007',
            #                 'match_source_label': 'Bronchoconstriction (HPO)',
            #                 'match_target': 'HP:0002104',
            #                 'match_target_label': 'Apnea (HPO)',
            #                 'score': 8.877204788271372,
            #                 'match_subsumer': None,
            #                 'match_subsumer_label': None,
            #                 'similarity': {
            #                     'subject_id': 'HP:4000007',
            #                     'subject_label': None,
            #                     'subject_source': None,
            #                     'object_id': 'HP:0002104',
            #                     'object_label': None,
            #                     'object_source': None,
            #                     'ancestor_id': 'HP:0002795',
            #                     'ancestor_label': '',
            #                     'ancestor_source': None,
            #                     'object_information_content': None,
            #                     'subject_information_content': None,
            #                     'ancestor_information_content': 8.877204788271372,
            #                     'jaccard_similarity': 0.72,
            #                     'cosine_similarity': None,
            #                     'dice_similarity': None,
            #                     'phenodigm_score': 2.5281589047279818
            #                 }
            #             }
            #         },
            #         'object_best_matches': {
            #             'HP:0002104': {
            #                 'match_source': 'HP:0002104',
            #                 'match_source_label': 'Apnea (HPO)',
            #                 'match_target': 'HP:0032933',
            #                 'match_target_label': 'Airway hyperresponsiveness (HPO)',
            #                 'score': 8.877204788271372,
            #                 'match_subsumer': None,
            #                 'match_subsumer_label': None,
            #                 'similarity': {
            #                     'subject_id': 'HP:0002104',
            #                     'subject_label': None,
            #                     'subject_source': None,
            #                     'object_id': 'HP:0032933',
            #                     'object_label': None,
            #                     'object_source': None,
            #                     'ancestor_id': 'HP:0002795',
            #                     'ancestor_label': '',
            #                     'ancestor_source': None,
            #                     'object_information_content': None,
            #                     'subject_information_content': None,
            #                     'ancestor_information_content': 8.877204788271372,
            #                     'jaccard_similarity': 0.782608695652174,
            #                     'cosine_similarity': None,
            #                     'dice_similarity': None,
            #                     'phenodigm_score': 2.6357878633126552
            #                 }
            #             },
            #             'HP:0012378': {
            #                 'match_source': 'HP:0012378',
            #                 'match_source_label': 'Fatigue (HPO)',
            #                 'match_target': 'HP:0032933',
            #                 'match_target_label': 'Airway hyperresponsiveness (HPO)',
            #                 'score': 4.059405129825457,
            #                 'match_subsumer': None,
            #                 'match_subsumer_label': None,
            #                 'similarity': {
            #                     'subject_id': 'HP:0012378',
            #                     'subject_label': None,
            #                     'subject_source': None,
            #                     'object_id': 'HP:0032933',
            #                     'object_label': None,
            #                     'object_source': None,
            #                     'ancestor_id': 'HP:0000118',
            #                     'ancestor_label': '',
            #                     'ancestor_source': None,
            #                     'object_information_content': None,
            #                     'subject_information_content': None,
            #                     'ancestor_information_content': 4.059405129825457,
            #                     'jaccard_similarity': 0.47619047619047616,
            #                     'cosine_similarity': None,
            #                     'dice_similarity': None,
            #                     'phenodigm_score': 1.3903417068554214
            #                 }
            #             }
            #         },
            #         'average_score': 6.704627500804806,
            #         'best_score': 8.877204788271372,
            #         'metric': 'ancestor_information_content'
            #     }
            # }
            #
            # TODO: Implement me!
            return dict()

        async def phenotype_semsim_to_disease(self, phenotype_ids: List[str]) -> Dict[str, List[str]]:
            """
            :param phenotype_ids: list of (HPO?) phenotype identifiers
            :type phenotype_ids: List[str]
            :return: Dictionary indexed by (MONDO) disease CURIEs
                     against lists of matching phenotype feature CURIEs
            :rtype: Dict[str, List[str]]
            """
            full_result: List[Dict] = await self.semsim_search(
                identifiers=phenotype_ids, group=SemsimSearchCategory.HGNC
            )
            result: Dict[str, List[str]] = self.parse_raw_semsim(full_result)
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
