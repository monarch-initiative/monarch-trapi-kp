"""
TRAPI JSON accessing data utilities
"""
from typing import Optional, List, Dict
from enum import Enum


class TargetQueryType(Enum):
    HP_IDS = "HP Ontology Term CURIEs"


def extract_trapi_parameters(
        trapi_json: Dict,
        target_query_input: TargetQueryType
) -> Optional[List[str]]:
    """
    Interprets the TRAPI JSON content to figure out what specific
    parameters are needed for the execution of the Monarch query.
    :param trapi_json: Dict, TRAPI Query JSON object
    :param target_query_input: TargetQueryInput, signal of type of input parameters to be extracted
    :return: Dict, TRAPI parameters required for a specified back end (Monarch) query
    """
    # First iteration will simply return the list of ids, assumed to be
    # HP ontology terms that are targets for the Monarch search
    # "message": {
    #       "query_graph": {
    #           "nodes": {
    # ...
    assert "message" in trapi_json
    assert "query_graph" in trapi_json["message"]
    assert "nodes" in trapi_json["message"]["query_graph"]
    nodes: Dict = trapi_json["message"]["query_graph"]
    for node_id, details in nodes.items():
        # Simplistic first implementation: return
        # the ids presumed to be HP ontology term CURIEs
        if target_query_input == TargetQueryType.HP_IDS:
            # ...
            #             "n0": {
            #               "categories": [
            #                 "biolink:PhenotypicEntity"
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
            if not("categories" in details and "ids" in details):
                continue
            if "biolink:PhenotypicEntity" in details["categories"]:
                return list(details["ids"])

        # elif or else... currently an unimplemented use case?

    return None


def build_trapi_message(results: Dict) -> Dict:
    # TODO: Implement me!
    return results
