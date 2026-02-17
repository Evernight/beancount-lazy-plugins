"""
A Beancount plugin that adds custom balance operations.

This plugin implements balance operations with a type parameter:

1. balance full: Expands into separate balance assertions for each currency.
   For currencies declared in the account's Open directive but not specified
   in the balance directive, creates balance assertions with amount 0.
   Example: 2015-01-01 custom "balance-ext" "full" Account 100 EUR 230 USD
   
2. balance padded: Generates pad directives on day-1, and creates balance assertions
   only for currencies explicitly provided in the directive.
   Example: 2015-01-01 custom "balance-ext" "padded" Account PadAccount 100 EUR 230 USD

3. balance full-padded: Combines full and padded behavior - asserts all declared currencies
   and generates pad directives on day-1
   Example: 2015-01-01 custom "balance-ext" "full-padded" Account PadAccount 100 EUR 230 USD

The Account "Open" instruction should specify all of the currencies used.
"""

import ast
import bisect
import collections
import datetime
from typing import NamedTuple

from beancount.core import data
from beancount.core import amount
from beancount.core.number import D
from beancount.parser.grammar import ValueType

from beancount.core.account import TYPE as ACCOUNT_TYPE

from .common import (
    BalanceType,
    BalanceExtendedError,
    build_account_currencies_mapping,
    get_directives_defined_config,
    is_balance_ext_config,
    parse_balance_extended_entry,
)

__plugins__ = ["balance_extended"]

class PadKey(NamedTuple):
    date: datetime.date
    account: str


def balance_extended(entries, options_map, config_str=None):
    """Extended version of the balance operation.
    
    It doesn't replace the original plugin but can be used in addition to it.

    Args:
      entries: A list of directives.
      options_map: A parser options dict.
      config_str: Optional configuration string (unused).
    Returns:
      A list of entries with balance operations expanded, 
      and a list of errors.
    """
    errors = []
    new_entries = []

    config = {}
    if config_str:
        try:
            config = ast.literal_eval(config_str)
        except (ValueError, SyntaxError) as e:
            errors.append(BalanceExtendedError(
                source=None,
                message=f"Invalid configuration string: {e}",
                entry=None
            ))
            return entries, errors

    default_pad_type = config.get("default_pad_type", "pad-ext")
    if default_pad_type == "pad-ext":
        plugin_names = [name for name, _ in options_map.get("plugin", [])]
        if "beancount_lazy_plugins.pad_extended" not in plugin_names:
            errors.append(BalanceExtendedError(
                source=None,
                message=(
                    "default_pad_type is 'pad-ext' but beancount_lazy_plugins.pad_extended "
                    "plugin is not enabled. Add plugin \"beancount_lazy_plugins.pad_extended\"."
                ),
                entry=None,
            ))
            return entries, errors

    balance_type_config = get_directives_defined_config(entries, errors)
    if errors:
        return entries, errors

    default_balance_type = config.get("default_balance_type", BalanceType.REGULAR.value)
    account_to_type_mapping: dict[str, str] = {}

    # Track Pad directives (both pre-existing and created by this plugin run) so we don't
    # emit duplicates for the same (date, account, source_account).
    existing_pad_keys: set[PadKey] = set()
    for entry in entries:
        if isinstance(entry, data.Pad):
            existing_pad_keys.add(PadKey(entry.date, entry.account))
        elif isinstance(entry, data.Custom) and entry.type == "pad-ext":
            account_value = None
            if entry.values:
                account_value = entry.values[0].value
            if isinstance(account_value, str):                
                existing_pad_keys.add(PadKey(entry.date, account_value))
    
    # Build mapping of account currencies from Open directives
    account_currencies = build_account_currencies_mapping(entries)

    balance_extended_parsed_entries = {}
    for entry in entries:
        if isinstance(entry, data.Custom) and entry.type == "balance-ext" and not is_balance_ext_config(entry):
            try:
                balance_extended_parsed_entries[id(entry)] = parse_balance_extended_entry(
                    entry,
                    account_to_type_mapping,
                    balance_type_config,
                    default_balance_type,
                )
            except BalanceExtendedError as exc:
                errors.append(exc)

    balance_dates_per_account = collections.defaultdict(list)
    for entry in entries:
        if isinstance(entry, data.Balance):
            balance_dates_per_account[entry.account].append(entry.date)
    for entry in balance_extended_parsed_entries.values():
        balance_dates_per_account[entry.account].append(entry.date)
    for account in balance_dates_per_account:
        balance_dates_per_account[account].sort()

    for entry in entries:
        if isinstance(entry, data.Custom):
            if entry.type == "balance-ext" and not is_balance_ext_config(entry):
                if not id(entry) in balance_extended_parsed_entries:
                    # already in errors, just skip here
                    continue

                balance_entries, entry_errors = process_balance(
                    balance_extended_parsed_entries[id(entry)],
                    entry,
                    account_currencies,
                    existing_pad_keys,
                    balance_dates_per_account,
                    config,
                )
                new_entries.extend(balance_entries)
                errors.extend(entry_errors)

                # pass original entry as well
                new_entries.append(entry)
            else:
                # Keep config and other custom directives as-is
                new_entries.append(entry)
        else:
            # Keep all non-custom directives as-is
            new_entries.append(entry)
    
    return new_entries, errors


def get_pad_and_prev_balance_date(date, balance_dates, config):
    """
    Get the best pad date and the previous balance date.
    The best pad date is the latest date that is after the previous balance date but before the current date.
    If no preferred pad dates are configured, the previous day is returned.
    """
    date_minus_one = date - datetime.timedelta(days=1)
    prev_balance_date = None
    index = bisect.bisect_right(balance_dates, date_minus_one)
    if index > 0:
        prev_balance_date = balance_dates[index - 1]

    preferred_pad_dates = config.get('preferred_pad_dates')
    if not preferred_pad_dates:
        return date_minus_one, prev_balance_date

    # find latest date that is after prev_balance_date but before the date
    best_date = None
    for candidate_month_date in [date, date - datetime.timedelta(days=31)]:
        for preferred_date in preferred_pad_dates:
            candidate_date = datetime.date(candidate_month_date.year, candidate_month_date.month, preferred_date)
            if (prev_balance_date is None or candidate_date >= prev_balance_date) and candidate_date < date and (best_date is None or candidate_date > best_date):
                best_date = candidate_date
    if best_date is None:
        best_date = date_minus_one
    return best_date, prev_balance_date

def process_balance(parsed_entry, custom_entry, account_currencies, existing_pad_keys, balance_dates_per_account, config):
    """Common logic for processing balance custom operations.
    
    Args:
      custom_entry: A Custom directive with type "balance-ext"
      account_currencies: Dictionary mapping account names to sets of currencies
      existing_pad_keys: A mutable set of already-seen pad keys to avoid duplicates
      balance_dates_per_account: A dictionary mapping account names to sets of dates
      config: A dictionary of configuration options
    Returns:
      A tuple of (list of new entries, list of errors)
    """
    errors = []
    new_entries = []

    account = parsed_entry.account
    balance_type = parsed_entry.balance_type
    amount_values = parsed_entry.amount_values

    new_meta = custom_entry.meta.copy()
    new_meta["generated_by"] = 'balance_extended'

    # For valuation type, just add a valuation entry
    if balance_type == BalanceType.VALUATION:
        new_entries.append(data.Custom(
            meta=new_meta,
            date=custom_entry.date,
            type="valuation",
            values=[ValueType(account, dtype=ACCOUNT_TYPE), ValueType(amount_values[0], dtype=amount.Amount)],
        ))
        return new_entries, errors

    # Add pad entry for padded balances
    if balance_type == BalanceType.PADDED or balance_type == BalanceType.FULL_PADDED:
        pad_account = custom_entry.meta.get("pad_account")

        pad_date, prev_balance_date = get_pad_and_prev_balance_date(custom_entry.date, balance_dates_per_account[account], config)

        pad_key = PadKey(pad_date, account)
        if pad_key not in existing_pad_keys:            
            pad_type = config.get('default_pad_type', 'pad-ext')
            pad_meta = new_meta
            pad_meta['end_balance_date'] = custom_entry.date.isoformat()
            pad_meta['start_balance_date'] = prev_balance_date.isoformat() if prev_balance_date else None

            if isinstance(pad_account, str):
                pad_meta["pad_account"] = pad_account

            if pad_type == 'pad-ext':
                pad_entry = data.Custom(
                    meta=pad_meta,
                    date=pad_date,
                    type="pad-ext",
                    values=[ValueType(account, dtype=ACCOUNT_TYPE)],
                )
            else:
                # when Pad is used, pad_account must be set in the metadata
                if not isinstance(pad_account, str):
                    errors.append(BalanceExtendedError(
                        new_meta,
                        "pad_account metadata must be set when 'default_pad_type' is 'pad'",
                        custom_entry,
                    ))
                    pad_entry = None
                else:
                    pad_entry = data.Pad(
                        meta=new_meta,
                        date=pad_date,
                        account=account,
                        source_account=pad_account,
                    )
            if pad_entry is not None:
                new_entries.append(pad_entry)
            existing_pad_keys.add(pad_key)
    
    # Parse explicit currency amounts from the directive
    explicit_currencies = {}
    for amount_obj in amount_values:
        explicit_currencies[amount_obj.currency] = amount_obj.number
    
    # Determine which currencies to create balance assertions for
    currencies_to_assert = set(explicit_currencies.keys())
    
    # For "full" and "full-padded" balance types, add all currencies from the account's Open directive.
    # For "padded", only assert currencies explicitly provided in the directive.
    if balance_type in (BalanceType.FULL, BalanceType.FULL_PADDED):
        account_declared_currencies = account_currencies.get(account, set())
        currencies_to_assert.update(account_declared_currencies)
    
    # Create balance assertions for all required currencies
    for currency in sorted(currencies_to_assert):  # Sort for consistent ordering
        amount_value = explicit_currencies.get(currency, D('0'))  # Default to 0 if not specified
        
        # Create a Balance directive
        balance_amount = amount.Amount(amount_value, currency)
        balance_entry = data.Balance(
            meta=new_meta,
            date=custom_entry.date,
            account=account,
            amount=balance_amount,
            tolerance=None,
            diff_amount=None
        )
        new_entries.append(balance_entry)
    if not currencies_to_assert:
        errors.append(BalanceExtendedError(
            custom_entry.meta,
            f"No currencies to assert for account {account}",
            custom_entry,
        ))
    
    return new_entries, errors
