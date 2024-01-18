"""
Shared Data Models declared here
"""
from typing import Union, List, Dict, Optional, Any

from mtkp.services.util.logutil import LoggingUtil
from mtkp.services.config import config

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)


DEFAULT_PROVENANCE = "infores:monarchinitiative"

TERM_DATA = Dict[str, str]
MATCH_LIST = List[TERM_DATA]
RESULT_ENTRY = Union[str, Dict[str, Union[str, List[Union[str, TERM_DATA]]]]]

# A RESULTS_MAP are RESULT_ENTRY matches indexed by SemSimian 'subject_id' hits
RESULTS_MAP = Dict[str, RESULT_ENTRY]

# The top level RESULT wrapper data type returns both its dataset
# plus some global metadata annotation, like global provenance
RESULT = Dict[str, Union[str, RESULTS_MAP]]


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
