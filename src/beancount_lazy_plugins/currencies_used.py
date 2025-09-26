"""
A Beancount plugin that tracks currencies used per account and adds metadata to Open directives.

This plugin goes through all transactions in the ledger and for each account keeps 
a set of currencies that have postings to this account. Then for each "open" account 
statement, it adds a metadata field 'currencies_used' that shows the list of these currencies.

When configured with 'extend_open_directives', it can also extend Open directives
with the actual currencies used:
- If currencies are not defined in Open directive, add the found used currencies
- If currencies are defined, validate they match the used currencies and report errors if not
"""

import collections
import ast
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
      config_str: Optional configuration string. Can contain 'extend_open_directives'.
    Returns:
      A list of entries with updated Open directives, and a list of errors.
    """
    errors = []
    
    # Parse configuration
    config = {}
    if config_str:
        try:
            config = ast.literal_eval(config_str)
        except (ValueError, SyntaxError) as e:
            errors.append(CurrenciesUsedError(
                source=None,
                message=f"Invalid configuration string: {e}",
                entry=None
            ))
            return entries, errors
    
    extend_open_directives = config.get('extend_open_directives', False)
    
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
            used_currencies = account_currencies.get(account, set())
            
            # Always add metadata if currencies were found
            new_meta = dict(entry.meta) if entry.meta else {}
            if used_currencies:
                sorted_used_currencies = sorted(list(used_currencies))
                new_meta['currencies_used'] = ', '.join(sorted_used_currencies)
            
            # Handle extend_open_directives configuration
            new_currencies = entry.currencies
            if extend_open_directives and used_currencies:
                sorted_used_currencies = sorted(list(used_currencies))
                
                if entry.currencies is None:
                    # No currencies defined in Open directive, add the used ones
                    new_currencies = sorted_used_currencies
                else:
                    # Currencies are defined, validate they match
                    defined_currencies = set(entry.currencies)
                    if defined_currencies != used_currencies:
                        # Create error for mismatch
                        defined_sorted = sorted(list(defined_currencies))
                        used_sorted = sorted(list(used_currencies))
                        errors.append(CurrenciesUsedError(
                            source=entry.meta,
                            message=f"Account {account}: defined currencies {defined_sorted} "
                                   f"do not match used currencies {used_sorted}",
                            entry=entry
                        ))
            
            # Create new Open directive
            new_open = Open(
                meta=new_meta,
                date=entry.date,
                account=entry.account,
                currencies=new_currencies,
                booking=entry.booking
            )
            new_entries.append(new_open)
        else:
            # Not an Open directive, keep as-is
            new_entries.append(entry)
    
    return new_entries, errors
