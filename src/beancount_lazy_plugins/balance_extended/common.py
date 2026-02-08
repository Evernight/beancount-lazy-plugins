"""
Common types and parsing utilities for balance-ext directives.

This module is designed to be used by other projects that need to parse
balance-ext custom directives without pulling in the full plugin logic.
"""

import datetime
import re
from enum import Enum
from typing import NamedTuple


class BalanceType(Enum):
    """Enum for balance operation types."""
    REGULAR = "regular"
    FULL = "full"
    PADDED = "padded"
    FULL_PADDED = "full-padded"
    VALUATION = "valuation"


BALANCE_TYPE_MAPPINGS = {
    "": BalanceType.REGULAR.value,
    "F": BalanceType.FULL.value,
    "~": BalanceType.PADDED.value,
    "F~": BalanceType.FULL_PADDED.value,
    "~F": BalanceType.FULL_PADDED.value,
    "!": BalanceType.REGULAR.value,
    "!F": BalanceType.FULL.value,
    "F!": BalanceType.FULL.value,
    "V": BalanceType.VALUATION.value,
}


class BalanceExtendedError(Exception):
    def __init__(self, source, message, entry):
        super().__init__(message)
        self.source = source
        self.message = message
        self.entry = entry


class BalanceExtended(NamedTuple):
    date: datetime.date
    account: str
    balance_type: BalanceType
    amount_values: list


class BalanceTypeConfig(NamedTuple):
    regex: re.Pattern
    balance_type: str


def parse_balance_extended_entry(custom_entry, config=None, balance_type_config=None):
    """Parse a balance-ext custom directive into a BalanceExtended tuple.

    Args:
      custom_entry: A beancount Custom directive with type "balance-ext".
      config: Optional dict of plugin configuration. Used to resolve
              ``default_balance_type`` when no explicit type is given and no
              account regex matches.
      balance_type_config: Optional list of BalanceTypeConfig entries that map
                           account regexes to balance types.

    Returns:
      A BalanceExtended named tuple.

    Raises:
      BalanceExtendedError: If the directive cannot be parsed.
    """
    if config is None:
        config = {}
    if balance_type_config is None:
        balance_type_config = []

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
            f"balance-ext requires the following arguments: {expected_format}",
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
