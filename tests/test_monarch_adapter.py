"""
Unit Tests for the Monarch Adapter
"""
from typing import List, Dict
import pytest

from mta.services.util import (
    TERM_DATA,
    MATCH_LIST,
    RESULT_ENTRY,
    RESULTS_MAP,
    RESULT,
    tag_value
)
from mta.services.util.monarch_adapter import SemsimSearchCategory, MonarchInterface
from mta.services.util.api_utils import get_monarch_interface

# def tag_value(json_data, tag_path) -> Optional[str]:

_TEST_JSON_DATA = {
        "testing": {
            "one": {
                "two": {
                    "three": "The End!"
                },

                "another_one": "for_fun"
            }
        }
    }


def test_valid_tag_path():
    value = tag_value(_TEST_JSON_DATA, "testing.one.two.three")
    assert value == "The End!"


def test_empty_tag_path():
    value = tag_value(_TEST_JSON_DATA, "")
    assert not value


def test_missing_intermediate_tag_path():
    value = tag_value(_TEST_JSON_DATA, "testing.one.four.five")
    assert not value


def test_missing_end_tag_path():
    value = tag_value(_TEST_JSON_DATA, "testing.one.two.three.four")
    assert not value


TEST_IDENTIFIERS = [
    "HP:0002104",
    "HP:0012378"
]


@pytest.mark.asyncio
async def test_semsim_search():
    monarch_interface: MonarchInterface = get_monarch_interface()
    semsim_result: List[Dict] = await monarch_interface.semsim_search(
        identifiers=TEST_IDENTIFIERS, group=SemsimSearchCategory.MONDO
    )
    assert semsim_result, "Semsimian search failed - empty result?"
    subject_id = tag_value(semsim_result[0], "subject.id")
    assert subject_id == "MONDO:0008807", "Expected Subject ID 'MONDO:0008807' not returned"
    object_termset: Dict = tag_value(semsim_result[0], "similarity.object_termset")
    assert object_termset, "Similarity Object term set is empty?"
    assert all([entry in object_termset.keys() for entry in object_termset])
    result: RESULTS_MAP = monarch_interface.parse_raw_semsim(
        full_result=semsim_result,
        match_category="biolink:PhenotypicFeature",
        ingest_knowledge_source="infores:hpo-annotation"
    )
    assert "MONDO:0008807" in result.keys()
    match_list: MATCH_LIST = result["MONDO:0008807"]["matches"]
    term_data: TERM_DATA
    assert all([term_data["id"] in ["HP:0002104", "HP:0012378"] for term_data in match_list])


@pytest.mark.asyncio
async def test_run_query():
    monarch_interface: MonarchInterface = get_monarch_interface()
    result: RESULT = await monarch_interface.run_query(identifiers=TEST_IDENTIFIERS)
    assert result
    assert "primary_knowledge_source" in result and result["primary_knowledge_source"] == "infores:semsimian-kp"
    assert "result_map" in result and result["result_map"]
    results_map: RESULTS_MAP = result["result_map"]
    assert "MONDO:0008807" in results_map.keys()
    result_entry: RESULT_ENTRY = results_map["MONDO:0008807"]
    match_list: MATCH_LIST = result_entry["matches"]
    term_data: TERM_DATA
    assert all([term_data["id"] in ["HP:0002104", "HP:0012378"] for term_data in match_list])
