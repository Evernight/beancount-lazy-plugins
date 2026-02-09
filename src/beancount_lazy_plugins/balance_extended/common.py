"""
Common types and parsing utilities for balance-ext directives.
"""

from __future__ import annotations

import datetime
import re
from decimal import Decimal
from enum import Enum
from typing import NamedTuple

from beancount.core import data
from beancount.core.data import Amount


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
    amount_values: list[Amount]


class BalanceTypeConfig(NamedTuple):
    regex: re.Pattern
    balance_type: str


def is_balance_ext_config(entry) -> bool:
    """Check if a Custom entry is a balance-ext config directive."""
    return (
        isinstance(entry, data.Custom)
        and entry.type == "balance-ext"
        and entry.values
        and isinstance(entry.values[0].value, str)
        and entry.values[0].value == "config"
    )


def build_account_currencies_mapping(entries):
    """Build a mapping of account names to their declared currencies."""
    account_currencies: dict[str, set[str]] = {}

    for entry in entries:
        if isinstance(entry, data.Open):
            if entry.currencies:
                account_currencies[entry.account] = set(entry.currencies)
            else:
                account_currencies[entry.account] = set()

    return account_currencies


def get_directives_defined_config(entries, errors):
    parsed_config = []
    config_entries = [
        entry
        for entry in entries
        if is_balance_ext_config(entry)
    ]
    for entry in reversed(config_entries):
        account_regex = entry.meta.get("account_regex")
        if not account_regex:
            errors.append(
                BalanceExtendedError(
                    entry.meta,
                    "account_regex is required in balance-ext config entry",
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
                    "balance_type is required in balance-ext config entry",
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


def build_account_type_mapping(
    accounts: list[str],
    balance_type_config: list[BalanceTypeConfig],
    default_balance_type: str,
) -> dict[str, str]:
    """Precompute default balance type per account."""
    mapping: dict[str, str] = {}
    for account in accounts:
        account_type = None
        for config_entry in balance_type_config:
            if config_entry.regex.match(account):
                account_type = config_entry.balance_type
                break
        if account_type is None:
            account_type = default_balance_type
        mapping[account] = account_type
    return mapping


def parse_balance_extended_entry(
    custom_entry,
    account_to_type_mapping: dict[str, str],
):
    """Parse a balance-ext custom directive into a BalanceExtended tuple."""
    values = custom_entry.values or []

    if values and isinstance(values[0].value, str) and values[0].value == "config":
        raise BalanceExtendedError(
            custom_entry.meta,
            "balance-ext config entries should not be parsed as balance entries",
            custom_entry,
        )

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
        if account not in account_to_type_mapping:
            raise BalanceExtendedError(
                custom_entry.meta,
                f"Missing default balance type for account {account}",
                custom_entry,
            )
        balance_type_str = account_to_type_mapping[account]

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

    raw_values = values[values_start_index:]
    amount_values: list[Amount] = []
    for value_wrapper in raw_values:
        obj = value_wrapper.value
        if isinstance(obj, Decimal) and obj == 0:
            continue
        if not isinstance(obj, Amount):
            raise BalanceExtendedError(
                custom_entry.meta,
                f"Expected Amount object, got {type(obj)}: {obj}",
                custom_entry,
            )
        amount_values.append(obj)

    return BalanceExtended(custom_entry.date, account, balance_type, amount_values)
"""
Common types and parsing utilities for balance-ext directives.
"""

import datetime
import re
from enum import Enum
from typing import NamedTuple

from beancount.core import data
from beancount.core.data import Amount


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


def parse_balance_extended_entry(custom_entry, config=None, balance_type_config=None):
    """Parse a balance-ext custom directive into a BalanceExtended tuple."""
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
