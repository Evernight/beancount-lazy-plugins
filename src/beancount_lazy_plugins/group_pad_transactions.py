"""
A Beancount plugin that allows to specify total investment account value over 
time and creates an underlying fictional commodity which price is set up to 
match total value of the account over time.

All incoming and outcoming transactions in and from account are converted into
transactions buying and selling this commodity at calculated price at the date.
"""

import collections

from beancount.core.data import Transaction
from beancount.core.data import Custom
from beancount.core.data import Price
from beancount.core.data import Amount
from beancount.core.data import Posting
from beancount.core.data import Commodity
from beancount.core.data import Balance
from beancount.core.position import CostSpec
from beancount.core.number import MISSING
import decimal
from decimal import Decimal
from beancount.parser import booking
from collections import defaultdict
from itertools import chain

__plugins__ = ['group_pad_transactions']

def group_pad_transactions(entries, options_map, config_str=None):
    result = []
    pad_transactions_by_groupping = defaultdict(list)
    for entry in entries:
        if isinstance(entry, Transaction) and entry.flag == 'P':
            if '(Padding inserted' in entry.narration:
                assert len(entry.postings) == 2, "pad transactions should have two postings"
                date = entry.date
                accounts = sorted([p.account for p in entry.postings])
                pad_transactions_by_groupping[(date, accounts[0], accounts[1])].append(entry)
        else:
            result.append(entry)
    for key, entries in pad_transactions_by_groupping.items():
        transaction = Transaction(
            meta=entries[0].meta,
            date=key[0],
            flag='*',
            payee=None,
            # narration='; '.join(e.narration for e in entries),
            narration=f'Padding (group of {len(entries)})' if len(entries) > 1 else entries[0].narration,
            tags=set(),
            links=set(),
            postings=list(chain(*[e.postings for e in entries]))
        )
        print(transaction)
        print('\n')
        result.append(transaction)

    return result, []