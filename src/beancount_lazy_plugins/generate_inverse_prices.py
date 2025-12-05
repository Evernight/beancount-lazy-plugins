"""A plugin that generates inverse price directives for all existing prices.

For each price directive like:
    2024-01-01 price USD 0.85 EUR

It will generate the inverse:
    2024-01-01 price EUR 1.176470588 USD

Unless the inverse price already exists in the price map for that date.
"""
from beancount.core import amount, data, prices
from collections import defaultdict
from decimal import Decimal

__plugins__ = ["generate"]


def generate(entries, options_map):
    errors = []
    priceMap = prices.build_price_map(entries)
    existingDates = defaultdict(set)

    # Pre-populate existing dates for all currency pairs
    for entry in entries:
        if isinstance(entry, data.Price):
            pair = (entry.currency, entry.amount.currency)
            existingDates[pair].add(entry.date)

    additionalEntries = []
    for entry in entries:
        if isinstance(entry, data.Price):
            # The inverse pair: if we have "price USD X EUR", inverse is "price EUR 1/X USD"
            inversePair = (entry.amount.currency, entry.currency)

            # Check if inverse price already exists for this date
            if entry.date in existingDates[inversePair]:
                continue

            # Calculate inverse rate
            if entry.amount.number == 0:
                continue

            inverseRate = Decimal(1) / entry.amount.number
            inverseAmount = amount.Amount(inverseRate, entry.currency)

            additionalEntries.append(
                data.Price(entry.meta, entry.date, entry.amount.currency, inverseAmount)
            )

            # Track the new entry to avoid duplicates within the same run
            existingDates[inversePair].add(entry.date)

    entries.extend(additionalEntries)

    return entries, errors

