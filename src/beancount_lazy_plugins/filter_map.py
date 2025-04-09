"""
A Beancount plugin that allows to apply filter+map operations over transactions in your ledger.

Filters are the same as Fava filters and even use the same code.
Possible operations are adding tags and metadata. A lot of effects can be achieved by using these and
other plugins in combination.
"""

import ast
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set, Dict, Any

from beancount.core.data import Custom, Transaction
from fava.core.fava_options import FavaOptions
from fava.core.filters import AccountFilter, AdvancedFilter, TimeFilter
from beancount.parser.grammar import ValueType


class OperationParams(Enum):
    TIME = "time"
    ACCOUNT = "account"
    ADVANCED = "filter"

    ADD_TAGS = "addTags"
    ADD_META = "addMeta"


ALL_OPERATION_PARAMS = [
    OperationParams.TIME,
    OperationParams.ACCOUNT,
    OperationParams.ADVANCED,
    OperationParams.ADD_TAGS,
    OperationParams.ADD_META,
]

__plugins__ = ["filter_map"]


@dataclass
class OperationConfig:
    """Configuration for a filter-map operation."""
    entry: Custom

    time: Optional[str] = None
    account: Optional[str] = None
    filter: Optional[str] = None

    addTags: Optional[str] = None
    addMeta: Optional[str] = None
    filters: List[Any] = field(default_factory=list)
    tagValues: List[str] = field(default_factory=list)
    times_applied: int = 0  # Track how many times this filter was applied


def matches_filter(entry, filter):
    if isinstance(filter, TimeFilter):
        return (
            entry.date >= filter.date_range.begin and entry.date < filter.date_range.end
        )
    else:
        return len(filter.apply([entry])) > 0


def filter_map(entries, options_map, config_str=None):
    presets = {}
    # read presets first
    for entry in entries:
        if (
            isinstance(entry, Custom)
            and entry.type == "filter-map"
            and entry.values[0].value.strip() == "preset"
        ):
            presets[entry.meta["name"]] = entry.meta

    # then form all operations
    operations = []
    for entry in entries:
        if (
            isinstance(entry, Custom)
            and entry.type == "filter-map"
            and entry.values[0].value.strip() == "apply"
        ):
            # Create a new OperationConfig instance
            config = OperationConfig(entry=entry)
            
            # Apply preset if available
            if "preset" in entry.meta:
                preset_name = entry.meta["preset"]
                preset_data = presets[preset_name]
                for param in ALL_OPERATION_PARAMS:
                    if param.value in preset_data:
                        setattr(config, param.value, preset_data[param.value])
            
            # Apply direct parameters
            for param in ALL_OPERATION_PARAMS:
                if param.value in entry.meta:
                    setattr(config, param.value, entry.meta[param.value])

            operations.append(config)

    # pre-calculate operation parameters defined by configuration
    for op in operations:
        filters = []

        if op.time:
            filters.append(
                TimeFilter(options_map, FavaOptions(), op.time)
            )
        if op.account:
            filters.append(AccountFilter(op.account))
        if op.filter:
            filters.append(AdvancedFilter(op.filter))

        # Store pre-calculated values
        op.filters = filters

        if op.addTags:
            op.tagValues = op.addTags.replace("#", "").split(" ")

    # now apply all operations to all entries (if necessary)
    new_entries = []
    for entry in entries:
        if (
            isinstance(entry, Custom)
            and entry.type == "filter-map"
            and entry.values[0].value.strip() == "apply"
        ):
            # ignore filter-map apply entries
            continue
        if not isinstance(entry, Transaction):
            # ignore non-Transactions
            new_entries.append(entry)
            continue

        new_entry = entry
        for op in operations:
            matched = True
            for f in op.filters:
                if not matches_filter(new_entry, f):
                    matched = False

            if matched:
                op.times_applied += 1  # Increment the apply count
                new_tags = new_entry.tags
                if op.addTags:
                    new_tags = set(new_entry.tags)
                    new_tags.update(op.tagValues)
                new_meta = new_entry.meta
                if op.addMeta:
                    new_meta_dict = ast.literal_eval(op.addMeta)
                    new_meta.update(new_meta_dict)

                transaction = Transaction(
                    new_meta,
                    new_entry.date,
                    flag=new_entry.flag,
                    payee=new_entry.payee,
                    narration=new_entry.narration,
                    tags=new_tags,
                    links=new_entry.links,
                    postings=new_entry.postings,
                )
                new_entry = transaction

        new_entries.append(new_entry)

    filter_map_entries = []
    # Add apply counts as metadata to the filter-map apply entries
    for i, op in enumerate(operations):
        entry = op.entry
        entry.meta["_timesApplied"] = op.times_applied
        # for better visibility in Fava
        if op.addTags:
            entry.values.append(ValueType(op.addTags, str))
        if op.filter:
            entry.values.append(ValueType(op.filter, str))

        filter_map_entries.append(entry)

    return filter_map_entries + new_entries, []
