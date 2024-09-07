"""
Testing a few low level MMCQ utilities here
"""
from typing import Optional, Tuple
import pytest
from mmcq.services.util.nodeinfo import get_node_details


@pytest.mark.parametrize(
    "curie,name,category",
    [
        ("", None, None),
        ("MONDO:0005662", "balantidiasis", "biolink:Disease"),
        ("MONDO:0005296", "sleep apnea syndrome", "biolink:Disease"),
        ("HP:0012378", "Fatigue", "biolink:PhenotypicFeature"),
        ("HGNC:12791", "WRN", "biolink:Gene")
    ]
)
def test_get_name(curie: str, name: Optional[str], category: Optional[str]):
    result: Optional[Tuple[str, str]] = get_node_details(curie)
    assert (not name and not result) or (name and result[0] == name and result[1] == category)
