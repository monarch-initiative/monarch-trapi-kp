"""
Shared Data Models declared here
"""
from typing import Union, List, Dict

TERM_DATA = Dict[str, str]
MATCH_LIST = List[TERM_DATA]
RESULT_ENTRY = Dict[str, Union[str, MATCH_LIST]]
RESULT_MAP = Dict[str, RESULT_ENTRY]
