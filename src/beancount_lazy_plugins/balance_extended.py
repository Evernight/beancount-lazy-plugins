"""
A Beancount plugin that adds custom balance operations.

This plugin implements balance operations with a type parameter:

1. balance full: Expands into separate balance assertions for each currency.
   For currencies declared in the account's Open directive but not specified
   in the balance directive, creates balance assertions with amount 0.
   Example: 2015-01-01 custom "balance-ext" "full" Account 100 EUR 230 USD
   
2. balance padded: Same as balance full but also generates pad directives on day-1
   Example: 2015-01-01 custom "balance-ext" "padded" Account PadAccount 100 EUR 230 USD

3. balance full-padded: Combines full and padded behavior - asserts all declared currencies
   and generates pad directives on day-1
   Example: 2015-01-01 custom "balance-ext" "full-padded" Account PadAccount 100 EUR 230 USD

The Account "Open" instruction should specify all of the currencies used.
"""

import collections
import datetime
from decimal import Decimal
from enum import Enum

from beancount.core import data
from beancount.core import amount
from beancount.core.number import D

__plugins__ = ["balance_extended"]

class BalanceType(Enum):
    """Enum for balance operation types."""
    FULL = "full"
    PADDED = "padded"
    FULL_PADDED = "full-padded"

BalanceExtendedError = collections.namedtuple(
    "BalanceExtendedError", "source message entry"
)


def balance_extended(entries, options_map, config_str=None):
    """Process balance custom operations with type parameter.
    
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
    
    # Build mapping of account currencies from Open directives
    account_currencies = build_account_currencies_mapping(entries)
    
    for entry in entries:
        if isinstance(entry, data.Custom):
            if entry.type == "balance-ext":
                # Process balance custom operation
                balance_entries, entry_errors = process_balance(entry, account_currencies)
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


def _extract_value(value_wrapper):
    """Extract the actual value from a ValueType wrapper or return the value directly.
    
    This handles both parsed values (wrapped in ValueType) and direct values (from tests).
    """
    if hasattr(value_wrapper, 'value'):
        return value_wrapper.value
    return value_wrapper


def process_balance(custom_entry, account_currencies):
    """Common logic for processing balance custom operations.
    
    Args:
      custom_entry: A Custom directive with type "balance-ext"
      account_currencies: Dictionary mapping account names to sets of currencies
    Returns:
      A tuple of (list of new entries, list of errors)
    """
    errors = []
    new_entries = []

    # Parse balance type from first parameter
    if len(custom_entry.values) < 1:
        errors.append(BalanceExtendedError(
            custom_entry.meta,
            "balance-ext directive requires at least balance_type parameter",
            custom_entry
        ))
        return new_entries, errors
    
    balance_type_str = _extract_value(custom_entry.values[0])
    if not isinstance(balance_type_str, str):
        errors.append(BalanceExtendedError(
            custom_entry.meta,
            "First argument to balance-ext must be balance type (string)",
            custom_entry
        ))
        return new_entries, errors
    
    try:
        balance_type = BalanceType(balance_type_str)
    except ValueError:
        errors.append(BalanceExtendedError(
            custom_entry.meta,
            f"Invalid balance type: {balance_type_str}. Must be 'full', 'padded', or 'full-padded'",
            custom_entry
        ))
        return new_entries, errors
    
    # Determine expected format and minimum arguments based on type
    if balance_type == BalanceType.FULL:
        min_args = 3  # balance_type + account + amount (minimum)
        expected_format = "balance_type account amount1 [amount2 ...]"
        values_start_index = 2
    elif balance_type == BalanceType.PADDED:
        min_args = 4  # balance_type + account + pad_account + amount (minimum)
        expected_format = "balance_type account pad_account amount1 [amount2 ...]"
        values_start_index = 3
    elif balance_type == BalanceType.FULL_PADDED:
        min_args = 4  # balance_type + account + pad_account + amount (minimum)
        expected_format = "balance_type account pad_account amount1 [amount2 ...]"
        values_start_index = 3
    else:
        raise ValueError(f"Invalid balance_type: {balance_type}")
    
    # Parse the custom directive values
    if len(custom_entry.values) < min_args:
        errors.append(BalanceExtendedError(
            custom_entry.meta,
            f"balance-ext {balance_type.value} requires at least {expected_format}",
            custom_entry
        ))
        return new_entries, errors
    
    account = _extract_value(custom_entry.values[1])
    if not isinstance(account, str):
        errors.append(BalanceExtendedError(
            custom_entry.meta,
            f"Second argument to balance-ext {balance_type.value} must be an account name (string)",
            custom_entry
        ))
        return new_entries, errors
    
    # Handle pad account for padded balances
    if balance_type == BalanceType.PADDED or balance_type == BalanceType.FULL_PADDED:
        pad_account = _extract_value(custom_entry.values[2])
        if not isinstance(pad_account, str):
            errors.append(BalanceExtendedError(
                custom_entry.meta,
                f"Third argument to balance-ext {balance_type.value} must be a pad account name (string)",
                custom_entry
            ))
            return new_entries, errors
        
        # Create pad directive on day-1
        pad_date = custom_entry.date - datetime.timedelta(days=1)
        pad_entry = data.Pad(
            meta=data.new_metadata("<balance_extended>", 0),
            date=pad_date,
            account=account,
            source_account=pad_account
        )
        new_entries.append(pad_entry)
    
    # Parse amount values (Beancount parses amounts as Amount objects)
    values = custom_entry.values[values_start_index:]
    
    # Parse explicit currency amounts from the directive
    explicit_currencies = {}
    
    # Handle Amount objects (Beancount parses amounts as Amount objects)
    for value_wrapper in values:
        amount_obj = _extract_value(value_wrapper)
        
        # Verify it's an Amount object
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
    
    # For "full", "padded", and "full-padded" balance types, add all currencies from the account's Open directive
    if balance_type in (BalanceType.FULL, BalanceType.PADDED, BalanceType.FULL_PADDED):
        account_declared_currencies = account_currencies.get(account, set())
        currencies_to_assert.update(account_declared_currencies)
    
    # Create balance assertions for all required currencies
    for currency in sorted(currencies_to_assert):  # Sort for consistent ordering
        amount_value = explicit_currencies.get(currency, D('0'))  # Default to 0 if not specified
        
        # Create a Balance directive
        balance_amount = amount.Amount(amount_value, currency)
        balance_entry = data.Balance(
            meta=data.new_metadata("<balance_extended>", 0),
            date=custom_entry.date,
            account=account,
            amount=balance_amount,
            tolerance=None,
            diff_amount=None
        )
        new_entries.append(balance_entry)
    
    return new_entries, errors
