"""
Unit Tests for the Monarch Adapter
"""
from typing import List, Dict
import pytest

from mta.services.util.monarch_adapter import SemsimSearchCategory, MonarchInterface
from mta.services.util.api_utils import get_monarch_interface


@pytest.mark.asyncio
async def test_semsim_search():
    phenotype_ids = [
        "HP:0002104",
        "HP:0012378",
        "HP:0012378",
        "HP:0012378"
    ]
    monarch_interface: MonarchInterface = get_monarch_interface()
    result: List[Dict] = await monarch_interface.semsim_search(
        identifiers=phenotype_ids, group=SemsimSearchCategory.HGNC
    )
    assert result

