"""
Some utilities for getting node information (i.e from NodeNormalizer)
"""
from sys import stderr
from typing import Optional, Dict, Tuple
from functools import lru_cache
import requests

CACHE_SIZE = 1024
NODE_NORMALIZER_SERVER = "https://nodenormalization-sri.renci.org/get_normalized_nodes"


def post_query(url: str, query: Dict, params=None, server: str = ""):
    """
    Post a JSON query to the specified URL and return the JSON response.

    :param url, str URL target for HTTP POST
    :param query, JSON query for posting
    :param params, optional parameters
    :param server, str human-readable name of server called (for error message reports)
    """
    if params is None:
        response = requests.post(url, json=query)
    else:
        response = requests.post(url, json=query, params=params)
    if not response.status_code == 200:
        print(
            f"Server {server} at '\nUrl: '{url}', Query: '{query}' with " +
            f"parameters '{params}' returned HTTP error code: '{response.status_code}'",
            file=stderr
        )
        return {}
    return response.json()


@lru_cache(CACHE_SIZE)
def get_node_details(curie: str) -> Optional[Tuple[str, str]]:
    """
    Returns the node name for a given CURIE
    :param curie: str, CURIE identifier of the node
    :return: Optional[Tuple[str, str]], name and category associated with the curie
    """
    j = {'curies': [curie]}
    result = post_query(NODE_NORMALIZER_SERVER, j)
    if not (result and curie in result and result[curie] and 'equivalent_identifiers' in result[curie]):
        return None
    name: Optional[str] = None
    category: Optional[str] = None
    if curie in result:
        if "id" in result[curie] and "label" in result[curie]["id"]:
            name = result[curie]["id"]["label"]
        if name:
            if "type" in result[curie] and result[curie]["type"]:
                category = result[curie]["type"][0]
            else:
                category = "biolink:NamedThing"
            return name, category

    return None
