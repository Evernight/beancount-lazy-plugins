"""
A Beancount plugin that tracks currencies used per account and adds metadata to Open directives.

This plugin goes through all transactions in the ledger and for each account keeps 
a set of currencies that have postings to this account. Then for each "open" account 
statement, it adds a metadata field 'currencies_used' that shows the list of these currencies.
"""

import collections
from beancount.core import data
from beancount.core.data import Open, Transaction

__plugins__ = ["currencies_used"]

CurrenciesUsedError = collections.namedtuple(
    "CurrenciesUsedError", "source message entry"
)

def currencies_used(entries, options_map, config_str=None):
    """Add currencies_used metadata to Open directives.
    
    Args:
      entries: A list of directives.
      options_map: A parser options dict.
      config_str: Optional configuration string (unused).
    Returns:
      A list of entries with updated Open directives, and a list of errors.
    """
    errors = []
    
    # Track currencies used per account
    account_currencies = collections.defaultdict(set)
    
    # First pass: collect all currencies used per account from transactions
    for entry in entries:
        if isinstance(entry, Transaction):
            for posting in entry.postings:
                if posting.units and posting.units.currency:
                    account_currencies[posting.account].add(posting.units.currency)
    
    # Second pass: update Open directives with currencies_used metadata
    new_entries = []
    
    for entry in entries:
        if isinstance(entry, Open):
            account = entry.account
            currencies = account_currencies.get(account, set())
            
            if currencies:
                # Sort currencies for consistent output
                sorted_currencies = sorted(list(currencies))
                
                # Create new metadata with currencies_used
                new_meta = dict(entry.meta) if entry.meta else {}
                new_meta['currencies_used'] = ', '.join(sorted_currencies)
                
                # Create new Open directive with updated metadata
                new_open = Open(
                    meta=new_meta,
                    date=entry.date,
                    account=entry.account,
                    currencies=entry.currencies,
                    booking=entry.booking
                )
                new_entries.append(new_open)
            else:
                # No currencies found for this account, keep original
                new_entries.append(entry)
        else:
            # Not an Open directive, keep as-is
            new_entries.append(entry)
    
    return new_entries, errors
