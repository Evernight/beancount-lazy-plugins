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
import copy
import datetime
import re
from decimal import Decimal
from enum import Enum
from typing import NamedTuple

from beancount.core import data
from beancount.core import amount
from beancount.core.number import D
from beancount.parser.grammar import ValueType

from beancount.core.account import TYPE as ACCOUNT_TYPE

__plugins__ = ["balance_extended"]

class BalanceType(Enum):
    """Enum for balance operation types."""
    REGULAR = "regular"
    FULL = "full"
    PADDED = "padded"
    FULL_PADDED = "full-padded"

BALANCE_TYPE_MAPPINGS = {    
    "": BalanceType.REGULAR.value,
    "F": BalanceType.FULL.value,
    "~": BalanceType.PADDED.value,
    "F~": BalanceType.FULL_PADDED.value,
    "~F": BalanceType.FULL_PADDED.value,
    "!": BalanceType.REGULAR.value,
    "!F": BalanceType.FULL.value,
    "F!": BalanceType.FULL.value,
}

class BalanceExtendedError(Exception):
    def __init__(self, source, message, entry):
        super().__init__(message)
        self.source = source
        self.message = message
        self.entry = entry

class PadKey(NamedTuple):
    date: datetime.date
    account: str


class BalanceExtended(NamedTuple):
    date: datetime.date
    account: str
    balance_type: BalanceType
    amount_values: list


class BalanceTypeConfig(NamedTuple):
    regex: re.Pattern
    balance_type: str


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

    balance_type_config = get_directives_defined_config(entries, errors)
    if errors:
        return entries, errors

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
        if isinstance(entry, data.Custom) and entry.type == "balance-ext":
            try:
                balance_extended_parsed_entries[id(entry)] = parse_balance_extended_entry(entry, config, balance_type_config)
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
            if entry.type == "balance-ext":
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
            else:
                # Keep other custom directives as-is
                new_entries.append(entry)
        else:
            # Keep all non-custom directives as-is
            new_entries.append(entry)
    
    return new_entries, errors


def build_account_currencies_mapping(entries):
    """Build a mapping of account names to their declared currencies.
    
    Args:
      entries: A list of directives.
    Returns:
      A dictionary mapping account names to sets of currency strings.
    """
    account_currencies = {}
    
    for entry in entries:
        if isinstance(entry, data.Open):
            if entry.currencies:
                account_currencies[entry.account] = set(entry.currencies)
            else:
                # If no currencies specified, use empty set
                account_currencies[entry.account] = set()
    
    return account_currencies


def get_directives_defined_config(entries, errors):
    parsed_config = []
    config_entries = [
        entry
        for entry in entries
        if isinstance(entry, data.Custom) and entry.type == "balance-ext-config"
    ]
    for entry in reversed(config_entries):
        account_regex = entry.meta.get("account_regex")
        if not account_regex:
            errors.append(
                BalanceExtendedError(
                    entry.meta,
                    "account_regex is required in balance-ext-config entry",
                    entry,
                )
            )
            continue
        try:
            compiled_account_regex = re.compile(account_regex)
        except re.error as exc:
            errors.append(
                BalanceExtendedError(
                    entry.meta,
                    f"Invalid account_regex: {exc}",
                    entry,
                )
            )
            continue
        balance_type = entry.meta.get("balance_type")
        if not isinstance(balance_type, str):
            errors.append(
                BalanceExtendedError(
                    entry.meta,
                    "balance_type is required in balance-ext-config entry",
                    entry,
                )
            )
            continue
        if balance_type in BALANCE_TYPE_MAPPINGS:
            balance_type = BALANCE_TYPE_MAPPINGS[balance_type]
        try:
            BalanceType(balance_type)
        except ValueError:
            errors.append(
                BalanceExtendedError(
                    entry.meta,
                    f"Invalid balance_type: {balance_type}. Must be 'full', 'padded', or 'full-padded'",
                    entry,
                )
            )
            continue
        parsed_config.append(BalanceTypeConfig(compiled_account_regex, balance_type))
    return parsed_config


def parse_balance_extended_entry(custom_entry, config, balance_type_config):
    values = custom_entry.values or []
    type_value = None
    if values and isinstance(values[0].value, str):
        candidate = values[0].value
        if candidate in BALANCE_TYPE_MAPPINGS or candidate in BALANCE_TYPE_MAPPINGS.values():
            type_value = candidate

    type_given = type_value is not None
    min_args = 3 if type_given else 2  # [type] + account + amount
    expected_format = "[balance_type] account amount1 [amount2 ...]"
    account_index = 1 if type_given else 0
    values_start_index = account_index + 1

    if len(values) < min_args:
        raise BalanceExtendedError(
            custom_entry.meta,
            f"balance-ext requires at least {expected_format}",
            custom_entry
        )

    account = values[account_index].value
    if not isinstance(account, str):
        raise BalanceExtendedError(
            custom_entry.meta,
            "Second argument to balance-ext must be an account name (string)",
            custom_entry
        )

    if type_given:
        balance_type_str = type_value
        if balance_type_str in BALANCE_TYPE_MAPPINGS:
            balance_type_str = BALANCE_TYPE_MAPPINGS[balance_type_str]
        elif balance_type_str not in BALANCE_TYPE_MAPPINGS.values():
            raise BalanceExtendedError(
                custom_entry.meta,
                f"Invalid balance type: {balance_type_str}. Must be 'full', 'padded', or 'full-padded'",
                custom_entry
            )
    else:
        balance_type_str = None
        for mapping in balance_type_config:
            if mapping.regex.match(account):
                balance_type_str = mapping.balance_type
                break
        if balance_type_str is None:
            balance_type_str = config.get("default_balance_type", BalanceType.REGULAR.value)

    if not isinstance(balance_type_str, str):
        raise BalanceExtendedError(
            custom_entry.meta,
            "balance_ext default_balance_type must be a string",
            custom_entry
        )

    try:
        balance_type = BalanceType(balance_type_str)
    except ValueError:
        raise BalanceExtendedError(
            custom_entry.meta,
            f"Invalid balance type: {balance_type_str}. Must be 'full', 'padded', or 'full-padded'",
            custom_entry
        )

    amount_values = values[values_start_index:]
    return BalanceExtended(custom_entry.date, account, balance_type, amount_values)


def get_pad_date(date, balance_dates, config):
    preferred_pad_dates = config.get('preferred_pad_dates')
    if not preferred_pad_dates:
        return date - datetime.timedelta(days=1)

    prev_balance_date = None
    index = bisect.bisect_right(balance_dates, date)
    if index > 0:
        prev_balance_date = balance_dates[index - 1]

    for month in [date.month, date.month - 1]:
        for preferred_date in reversed(sorted(preferred_pad_dates)):
            candidate_date = datetime.date(date.year, month, preferred_date)
            if candidate_date < date and candidate_date >= prev_balance_date:
                return candidate_date
    return date - datetime.timedelta(days=1)

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

    # Add pad entry for padded balances
    if balance_type == BalanceType.PADDED or balance_type == BalanceType.FULL_PADDED:
        pad_account = custom_entry.meta.get("pad_account")

        pad_date = get_pad_date(custom_entry.date, balance_dates_per_account[account], config)

        pad_key = PadKey(pad_date, account)
        if pad_key not in existing_pad_keys:            
            pad_type = config.get('default_pad_type', 'pad-ext')
            if pad_type == 'pad-ext':
                pad_entry = data.Custom(
                    meta=custom_entry.meta.copy(),
                    date=pad_date,
                    type="pad-ext",
                    values=[ValueType(account, dtype=ACCOUNT_TYPE)],
                )
            else:
                # when Pad is used, pad_account must be set in the metadata
                if not isinstance(pad_account, str):
                    errors.append(BalanceExtendedError(
                        custom_entry.meta,
                        "pad_account metadata must be set when 'default_pad_type' is 'pad'",
                        custom_entry,
                    ))
                    pad_entry = None
                else:
                    pad_entry = data.Pad(
                        meta=custom_entry.meta.copy(),
                        date=pad_date,
                        account=account,
                        source_account=pad_account,
                    )
            if pad_entry is not None:
                pad_entry.meta['generated_by'] = "balance-ext"
                if isinstance(pad_account, str):
                    pad_entry.meta["pad_account"] = pad_account
                new_entries.append(pad_entry)
            existing_pad_keys.add(pad_key)
    
    # Parse explicit currency amounts from the directive
    explicit_currencies = {}
    
    # Handle Amount objects (Beancount parses amounts as Amount objects)
    for value_wrapper in amount_values:
        amount_obj = value_wrapper.value
        
        # Allow to put just 0 to specify empty balance
        if isinstance(amount_obj, Decimal) and amount_obj == 0:
            continue
        # Otherwise verify it's an Amount object
        if not isinstance(amount_obj, amount.Amount):
            errors.append(BalanceExtendedError(
                custom_entry.meta,
                f"Expected Amount object, got {type(amount_obj)}: {amount_obj}",
                custom_entry
            ))
            continue
        
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
            meta=custom_entry.meta.copy(),
            date=custom_entry.date,
            account=account,
            amount=balance_amount,
            tolerance=None,
            diff_amount=None
        )
        new_entries.append(balance_entry)
    
    return new_entries, errors
