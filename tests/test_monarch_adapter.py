"""
Unit Tests for the Monarch Adapter
"""
from typing import List, Dict
import pytest
from deepdiff.diff import DeepDiff

from mmcq.services.config import config
from mmcq.services.util import (
    DEFAULT_PROVENANCE,
    TERM_DATA,
    MATCH_LIST,
    RESULT_ENTRY,
    RESULTS_MAP,
    RESULT,
    tag_value
)
from mmcq.services.util.monarch_adapter import SemsimSearchCategory, MonarchInterface
from mmcq.services.util.api_utils import get_example, get_monarch_interface
from mmcq.services.util.question import Question

test_resource_id: str = config.get('provenance_tag', DEFAULT_PROVENANCE)

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


TEST_TRAPI_QUERY: Dict = get_example("reasoner-trapi-1.5")
TEST_TRAPI_MESSAGE = TEST_TRAPI_QUERY["message"]
TEST_IDENTIFIERS = tag_value(TEST_TRAPI_MESSAGE, "query_graph.nodes.phenotypes.member_ids")


@pytest.mark.asyncio
async def test_semsim_search():
    monarch_interface: MonarchInterface = get_monarch_interface()

    # The success of this test depends a bit on the contents of
    # Monarch and the SemSimian algorithm as of January 2024
    semsim_result: List[Dict] = await monarch_interface.semsim_search(
        query_terms=TEST_IDENTIFIERS,
        group=SemsimSearchCategory.MONDO,
        result_limit=5
    )
    assert semsim_result, "Semsimian search failed - empty result?"
    subject_id = tag_value(semsim_result[0], "subject.id")
    assert subject_id == "MONDO:0008807", "Expected Subject ID 'MONDO:0008807' not returned"
    object_termset: Dict = tag_value(semsim_result[0], "similarity.object_termset")
    assert object_termset, "Similarity Object term set is empty?"
    assert all([entry in object_termset.keys() for entry in object_termset])
    result: RESULTS_MAP = monarch_interface.parse_raw_semsim(
        full_result=semsim_result,
        match_category="biolink:PhenotypicFeature"
    )
    assert "MONDO:0008807" in result.keys()
    match_list: MATCH_LIST = result["MONDO:0008807"]["matches"]
    term_data: TERM_DATA
    assert all(
        [
            term_data["object_id"] in ["HP:0002104", "HP:0012378"] and
            term_data["category"] == "biolink:PhenotypicFeature"
            for term_data in match_list
        ]
    )


@pytest.mark.asyncio
async def test_run_query():
    monarch_interface: MonarchInterface = get_monarch_interface()
    result: RESULT = await monarch_interface.run_query(
        trapi_message=TEST_TRAPI_MESSAGE, result_limit=5
    )
    assert result
    assert "primary_knowledge_source" in result and result["primary_knowledge_source"] == "infores:semsimian-kp"
    assert "result_map" in result and result["result_map"]
    results_map: RESULTS_MAP = result["result_map"]
    assert "MONDO:0008807" in results_map.keys()
    result_entry: RESULT_ENTRY = results_map["MONDO:0008807"]
    match_list: MATCH_LIST = result_entry["matches"]
    term_data: TERM_DATA
    assert all(
        [
            term_data["object_id"] in ["HP:0002104", "HP:0012378"] and
            term_data["category"] == "biolink:PhenotypicFeature"
            for term_data in match_list
        ]
    )


@pytest.mark.parametrize(
    "sources,output",
    [
        (   # Query 0 - Empty sources, return instance of top level system source
            [],
            [
                {
                    "resource_id": test_resource_id,
                    "resource_role": "aggregator_knowledge_source",
                    "source_record_urls": None,
                    "upstream_resource_ids": None
                }
            ]
        ),
        (   # Query 1 - Add primary knowledge source
            [
                {
                    "resource_id": "infores:semsimian-kp",
                    "resource_role": "primary_knowledge_source"
                }
            ],
            [
                {
                    "resource_id": "infores:semsimian-kp",
                    "resource_role": "primary_knowledge_source",
                    "source_record_urls": None,
                    "upstream_resource_ids": None
                },
                {
                    "resource_id": test_resource_id,
                    "resource_role": "aggregator_knowledge_source",
                    "source_record_urls": None,
                    "upstream_resource_ids":  ["infores:semsimian-kp"]
                }
            ]
        ),
        (   # Query 2 - Add a supporting data source, below the primary knowledge source
            [
                {
                    "resource_id": "infores:semsimian-kp",
                    "resource_role": "primary_knowledge_source"
                },
                {
                    "resource_id": "infores:hpo-annotations",
                    "resource_role": "supporting_data_source"
                }
            ],
            [
                {
                    "resource_id": "infores:semsimian-kp",
                    "resource_role": "primary_knowledge_source",
                    "source_record_urls": None,
                    "upstream_resource_ids": ["infores:hpo-annotations"]
                },
                {
                    "resource_id": "infores:hpo-annotations",
                    "resource_role": "supporting_data_source",
                    "source_record_urls": None,
                    "upstream_resource_ids": None
                },
                {
                    "resource_id": test_resource_id,
                    "resource_role": "aggregator_knowledge_source",
                    "source_record_urls": None,
                    "upstream_resource_ids":  ["infores:semsimian-kp"]
                }
            ]
        ),
        (   # Query 3 - Add a supporting data source, below the main application
            #           aggregator (lacking primary knowledge source)
            [
                {
                    "resource_id": "infores:hpo-annotations",
                    "resource_role": "supporting_data_source"
                }
            ],
            [
                {
                    "resource_id": "infores:hpo-annotations",
                    "resource_role": "supporting_data_source",
                    "source_record_urls": None,
                    "upstream_resource_ids": None
                },
                {
                    "resource_id": test_resource_id,
                    "resource_role": "aggregator_knowledge_source",
                    "source_record_urls": None,
                    "upstream_resource_ids":  ["infores:hpo-annotations"]
                }
            ]
        ),
        (   # Query 4 - Same query as 3 above except adding some
            #           source_record_urls for the supporting data source
            [
                {
                    "resource_id": "infores:hpo-annotations",
                    "resource_role": "supporting_data_source",
                    "source_record_urls": ["https://hpo.jax.org/app/"]
                }
            ],
            [
                {
                    "resource_id": "infores:hpo-annotations",
                    "resource_role": "supporting_data_source",
                    "source_record_urls": ["https://hpo.jax.org/app/"],
                    "upstream_resource_ids": None
                },
                {
                    "resource_id": test_resource_id,
                    "resource_role": "aggregator_knowledge_source",
                    "source_record_urls": None,
                    "upstream_resource_ids":  ["infores:hpo-annotations"]
                }
            ]
        ),
        (   # Query 5 - Same query as 3 above except adding a second "supporting_data_source"
            [
                {
                    "resource_id": "infores:hpo-annotations",
                    "resource_role": "supporting_data_source"
                },
                {
                    "resource_id": "infores:upheno",
                    "resource_role": "supporting_data_source"
                }
            ],
            [
                {
                    "resource_id": "infores:hpo-annotations",
                    "resource_role": "supporting_data_source",
                    "source_record_urls": None,
                    "upstream_resource_ids": None
                },
                {
                    "resource_id": "infores:upheno",
                    "resource_role": "supporting_data_source",
                    "source_record_urls": None,
                    "upstream_resource_ids": None
                },
                {
                    "resource_id": test_resource_id,
                    "resource_role": "aggregator_knowledge_source",
                    "source_record_urls": None,
                    "upstream_resource_ids":  ["infores:hpo-annotations","infores:upheno"]
                }
            ]
        )
    ]
)
def test_source_construct_sources_tree(sources: List[Dict], output: List[Dict]):
    # dummy Question - don't care about input question JSON for this test...
    question: Question = Question(question_json={}, result_limit=0)
    # ... 'cuz comparing sources tree directly
    formatted_sources = question._construct_sources_tree(sources)
    assert not DeepDiff(output, formatted_sources, ignore_order=True, report_repetition=True)
