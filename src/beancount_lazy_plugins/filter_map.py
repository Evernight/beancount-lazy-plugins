"""
A Beancount plugin that allows to apply filter+map operations over transactions in your ledger.

Filters are the same as Fava filters and even use the same code.
Possible operations are adding tags and metadata. A lot of effects can be achieved by using these and
other plugins in combination.
"""

import ast
from enum import Enum

from beancount.core.data import Custom, Transaction
from fava.core.fava_options import FavaOptions
from fava.core.filters import AccountFilter, AdvancedFilter, TimeFilter


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
            params = {}
            if "preset" in entry.meta:
                params = presets[entry.meta["preset"]]
            for param in ALL_OPERATION_PARAMS:
                if param.value in entry.meta:
                    params[param.value] = entry.meta[param.value]
            operations.append(params)

    # pre-calculate operation parameters defined by configuration
    for op in operations:
        filters = []

        if OperationParams.TIME.value in op:
            filters.append(
                TimeFilter(options_map, FavaOptions(), op[OperationParams.TIME.value])
            )
        if OperationParams.ACCOUNT.value in op:
            filters.append(AccountFilter(op[OperationParams.ACCOUNT.value]))
        if OperationParams.ADVANCED.value in op:
            filters.append(AdvancedFilter(op[OperationParams.ADVANCED.value]))

        # a bit hacky but just store pre-calculated values in the same dictionary
        op["filters"] = filters

        if OperationParams.ADD_TAGS.value in op:
            op["tagValues"] = (
                op[OperationParams.ADD_TAGS.value].replace("#", "").split(" ")
            )

    # now apply all operations to all entries (if necessary)
    new_entries = []
    for entry in entries:
        if not isinstance(entry, Transaction):
            # ignore non-Transactions
            new_entries.append(entry)
            continue

        new_entry = entry
        for op in operations:
            matched = True
            for f in op["filters"]:
                if not matches_filter(new_entry, f):
                    matched = False

            if matched:
                new_tags = new_entry.tags
                if OperationParams.ADD_TAGS.value in op:
                    new_tags = set(new_entry.tags)
                    new_tags.update(op["tagValues"])
                new_meta = new_entry.meta
                if OperationParams.ADD_META.value in op:
                    new_meta_dict = ast.literal_eval(op[OperationParams.ADD_META.value])
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

    return new_entries, []
