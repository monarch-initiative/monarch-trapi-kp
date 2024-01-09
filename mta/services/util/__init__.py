"""
Shared Data Models declared here
"""
from typing import Union, List, Dict

TERM_DATA = Dict[str, str]
MATCH_LIST = List[TERM_DATA]
RESULT_ENTRY = Union[str, Dict[str, Union[str, MATCH_LIST]]]
RESULTS_MAP = Dict[str, RESULT_ENTRY]

# The top level RESULT wrapper data type returns both
# its dataset plus some metadata annotation
RESULT = Dict[str, Union[str, RESULTS_MAP]]
