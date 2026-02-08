"""
Common types and parsing utilities for valuation directives.

This module is designed to be used by other projects that need to parse
valuation custom directives without pulling in the full plugin logic.
"""

import datetime
from typing import NamedTuple

from beancount.core.data import Amount


class ValuationError(Exception):
    def __init__(self, source, message, entry):
        super().__init__(message)
        self.source = source
        self.message = message
        self.entry = entry


class ParsedValuation(NamedTuple):
    date: datetime.date
    account: str
    amount: Amount  # beancount Amount with .number and .currency


def parse_valuation_entry(custom_entry):
    """Parse a valuation custom directive into a ParsedValuation tuple.

    Expects a Custom directive of type "valuation" with two values:
    ``account`` (string) and ``amount`` (beancount Amount).

    Config entries (where ``values[0].value == "config"``) are rejected
    with a :class:`ValuationError`.

    Args:
      custom_entry: A beancount Custom directive with type "valuation".

    Returns:
      A ParsedValuation named tuple.

    Raises:
      ValuationError: If the directive cannot be parsed.
    """
    values = custom_entry.values or []

    if not values:
        raise ValuationError(
            custom_entry.meta,
            "valuation directive requires at least 2 arguments: account amount",
            custom_entry,
        )

    # Skip config entries
    if values[0].value == "config":
        raise ValuationError(
            custom_entry.meta,
            "valuation config entries should not be parsed as valuation entries",
            custom_entry,
        )

    if len(values) < 2:
        raise ValuationError(
            custom_entry.meta,
            "valuation directive requires 2 arguments: account amount",
            custom_entry,
        )

    account = values[0].value
    if not isinstance(account, str):
        raise ValuationError(
            custom_entry.meta,
            "First argument to valuation must be an account name (string)",
            custom_entry,
        )

    valuation_amount = values[1].value
    if not isinstance(valuation_amount, Amount):
        raise ValuationError(
            custom_entry.meta,
            f"Second argument to valuation must be an Amount, got {type(valuation_amount)}",
            custom_entry,
        )

    return ParsedValuation(custom_entry.date, account, valuation_amount)
