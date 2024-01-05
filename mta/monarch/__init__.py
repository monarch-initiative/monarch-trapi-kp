"""
Interfaces assessing Monarch Initiative
"""
from typing import List, Dict
from enum import Enum


class SemsimSearchCategory(Enum):
    HGNC = "Human Genes"
    MGI = "Mouse Genes"
    RGD = "Rat Genes"
    ZFIN = "Zebrafish Genes"
    WB = "C. Elegans Genes"
    MONDO = "Human Diseases"


class Monarch:

    def __init__(self):
        pass

    @staticmethod
    def get_phenotype_ids(trapi_query: Dict) -> List[str]:
        return list()

    @staticmethod
    def semsim_search(
            identifiers: List[str],
            group: SemsimSearchCategory = SemsimSearchCategory.HGNC
    ) -> Dict[str, List[str]]:
        # curl -X 'POST' \
        #   'http://api-v3.monarchinitiative.org/v3/api/semsim/search' \
        #   -H 'accept: application/json' \
        #   -H 'Content-Type: application/json' \
        #   -d '{
        #   "termset": ["HP:0002104", "HP:0012378", "HP:0012378", "HP:0012378"],
        #   "group": "Human Diseases",
        #   "limit": 5
        # }'
        return dict()

    def phenotype_semsim_to_disease(self, trapi_query: Dict) -> Dict[str, List[str]]:
        """
        :param trapi_query: Python dictionary version of TRAPI Query JSON
        :type trapi_query: Dict
        :return: Dictionary indexed by (MONDO) disease CURIEs
                 against lists of matching phenotype feature CURIEs
        :rtype: Dict[str, List[str]]
        """
        hp_ids: List[str] = self.get_phenotype_ids(trapi_query)
        result: Dict[str, List[str]] = self.semsim_search(identifiers=hp_ids)
        return result
