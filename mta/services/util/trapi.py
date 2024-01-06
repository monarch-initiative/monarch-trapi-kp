"""
TRAPI JSON accessing data utilities
"""
from typing import Dict


def extract_trapi_parameters(
        trapi_json: Dict
) -> Dict:
    """
    Interprets the TRAPI JSON content to figure out what specific
    parameters are needed for the execution of the Monarch query.
    :param trapi_json:
    :return: Dict, TRAPI parameters required for a specified back end (Monarch) query
    """
    # TODO: Implement me!
    return trapi_json


def build_trapi_message(results: Dict) -> Dict:
    # TODO: Implement me!
    return results
