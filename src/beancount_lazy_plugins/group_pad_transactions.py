"""
This plugin improves treatment of pad/balance operations, in partucular  if you use them following
this guide: https://lazy-beancount.xyz/docs/stage1_totals/explanation/

If you have multiple currencies in the single account, multiple pad transactions will be generated.
However, if some of these correspond to currency conversions that you don't specify explicitly
(and I think that's way too much hassle), the groups of pad operations may create too much noise when
you look at transaction journal and tables. This plugin combines these groups into a single transaction.
"""

import collections
import decimal
from collections import defaultdict
from decimal import Decimal
from itertools import chain

from beancount.core.data import (
    Amount,
    Balance,
    Commodity,
    Custom,
    Posting,
    Price,
    Transaction,
)
from beancount.core.number import MISSING
from beancount.core.position import CostSpec
from beancount.parser import booking

__plugins__ = ["group_pad_transactions"]


def group_pad_transactions(entries, options_map, config_str=None):
    result = []
    pad_transactions_by_groupping = defaultdict(list)
    for entry in entries:
        if isinstance(entry, Transaction) and entry.flag == "P":
            if "(Padding inserted" in entry.narration:
                assert len(entry.postings) == 2, (
                    "pad transactions should have two postings"
                )
                date = entry.date
                accounts = sorted([p.account for p in entry.postings])
                pad_transactions_by_groupping[(date, accounts[0], accounts[1])].append(
                    entry
                )
        else:
            result.append(entry)
    for key, entries in pad_transactions_by_groupping.items():
        transaction = Transaction(
            meta=entries[0].meta,
            date=key[0],
            flag="*",
            payee=None,
            # narration='; '.join(e.narration for e in entries),
            narration=(
                f"Padding (group of {len(entries)})"
                if len(entries) > 1
                else entries[0].narration
            ),
            tags=set(),
            links=set(),
            postings=list(chain(*[e.postings for e in entries])),
        )
        result.append(transaction)

    return result, []
