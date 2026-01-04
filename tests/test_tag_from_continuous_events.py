"""
Tests for the tag_from_continuous_events plugin functionality.
"""

from pathlib import Path

import pytest
from beancount import loader
from beancount.core.data import Transaction


def test_tag_from_continuous_events_example_ledger():
    input_path = (
        Path("tests") / "data" / "tag_from_continuous_events_example.beancount"
    )

    entries, errors, _options_map = loader.load_file(str(input_path))
    if errors:
        pytest.fail(f"Failed to load test ledger: {errors}")

    txns = [e for e in entries if isinstance(e, Transaction)]
    assert len(txns) == 3

    by_narration = {t.narration: t for t in txns}
    coffee = by_narration["Coffee"]
    museum = by_narration["Museum tickets"]
    shopping = by_narration["Online shopping"]

    assert "location-London" in coffee.tags
    assert "location-Bangkok" in museum.tags
    assert "location-London" not in shopping.tags


