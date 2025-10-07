"""
A Beancount plugin that converts postings based on convert_to metadata.

This plugin goes through all postings in all transactions and, if a posting has
a convert_to: "<target_currency>" metadata, will replace it with a posting that
is in the target currency (converted at the date of the transaction using the
price map).
"""

import collections
from decimal import Decimal
from beancount.core import data, prices
from beancount.core.data import Amount, Posting, Transaction

__plugins__ = ["currency_convert"]

CurrencyConvertError = collections.namedtuple(
    "CurrencyConvertError", "source message entry"
)

CONVERT_TO_METADATA_KEY = "convert_to"
AT_TODAY_PRICE_METADATA_KEY = "at_today_price_in"

def currency_convert(entries, options_map, config_str=None):
    """Convert postings based on convert_to metadata.
    
    Args:
      entries: A list of directives.
      options_map: A parser options dict.
      config_str: Optional configuration string (unused).
    Returns:
      A list of entries with converted postings, and a list of errors.
    """
    errors = []
    new_entries = []
    
    # Build the price map from all entries
    price_map = prices.build_price_map(entries)
    
    for entry in entries:
        if isinstance(entry, Transaction):
            transaction_modified = False
            new_postings = []
            
            for posting in entry.postings:
                # Check if this posting has convert_to metadata
                convert_to = posting.meta.get(CONVERT_TO_METADATA_KEY) if posting.meta else None
                at_today_price = posting.meta.get(AT_TODAY_PRICE_METADATA_KEY) if posting.meta else None
                
                if convert_to and posting.units:
                    # Get the source currency from the posting
                    source_currency = posting.units.currency
                    target_currency = convert_to
                    
                    if source_currency == target_currency:
                        # No conversion needed, just remove the metadata
                        new_meta = dict(posting.meta) if posting.meta else {}
                        new_meta.pop(CONVERT_TO_METADATA_KEY, None)
                        new_posting = posting._replace(meta=new_meta if new_meta else None)
                        new_postings.append(new_posting)
                        transaction_modified = True
                    else:
                        # Look up the exchange rate
                        currency_pair = (source_currency, target_currency)
                        price_info = prices.get_price(price_map, currency_pair, entry.date)
                        
                        if price_info[1] is None:
                            # No price found, try the inverse
                            inverse_pair = (target_currency, source_currency)
                            inverse_price_info = prices.get_price(price_map, inverse_pair, entry.date)
                            
                            if inverse_price_info[1] is None:
                                # Still no price found, report error and keep original posting
                                errors.append(CurrencyConvertError(
                                    posting.meta or {},
                                    f"No price found for conversion from {source_currency} to {target_currency} on {entry.date}",
                                    entry
                                ))
                                new_postings.append(posting)
                            else:
                                # Use inverse rate
                                exchange_rate = Decimal(1) / inverse_price_info[1]
                                converted_amount = posting.units.number * exchange_rate
                                # Set per-unit price in terms of the original currency so that
                                # converted amount can be traced back to the source currency.
                                new_price = Amount(Decimal(1) / exchange_rate, source_currency)
                                
                                # Create new posting with converted amount and updated metadata
                                new_meta = dict(posting.meta) if posting.meta else {}
                                new_meta.pop(CONVERT_TO_METADATA_KEY, None)
                                # Add converted_from metadata with original amount and currency
                                new_meta['converted_from'] = f"{posting.units.number} {source_currency}"
                                
                                new_posting = Posting(
                                    account=posting.account,
                                    units=Amount(converted_amount, target_currency),
                                    cost=posting.cost,
                                    price=new_price,
                                    flag=posting.flag,
                                    meta=new_meta if new_meta else None
                                )
                                new_postings.append(new_posting)
                                transaction_modified = True
                        else:
                            # Use direct rate
                            exchange_rate = price_info[1]
                            converted_amount = posting.units.number * exchange_rate
                            # Set per-unit price in terms of the original currency so that
                            # converted amount can be traced back to the source currency.
                            new_price = Amount(Decimal(1) / exchange_rate, source_currency)
                            
                            # Create new posting with converted amount and updated metadata
                            new_meta = dict(posting.meta) if posting.meta else {}
                            new_meta.pop(CONVERT_TO_METADATA_KEY, None)
                            # Add converted_from metadata with original amount and currency
                            new_meta['converted_from'] = f"{posting.units.number} {source_currency}"
                            
                            new_posting = Posting(
                                account=posting.account,
                                units=Amount(converted_amount, target_currency),
                                cost=posting.cost,
                                price=new_price,
                                flag=posting.flag,
                                meta=new_meta if new_meta else None
                            )
                            new_postings.append(new_posting)
                            transaction_modified = True
                elif at_today_price and posting.units:
                    source_currency = posting.units.currency
                    target_currency = at_today_price
                    if source_currency == target_currency:
                        # No pricing needed, just remove the metadata
                        new_meta = dict(posting.meta) if posting.meta else {}
                        new_meta.pop(AT_TODAY_PRICE_METADATA_KEY, None)
                        new_posting = posting._replace(meta=new_meta if new_meta else None)
                        new_postings.append(new_posting)
                        transaction_modified = True
                    else:
                        # Look up the price at the transaction date
                        currency_pair = (source_currency, target_currency)
                        price_info = prices.get_price(price_map, currency_pair, entry.date)
                        if price_info[1] is None:
                            # Try inverse
                            inverse_pair = (target_currency, source_currency)
                            inverse_price_info = prices.get_price(price_map, inverse_pair, entry.date)
                            if inverse_price_info[1] is None:
                                # No price found; keep original and record error
                                errors.append(CurrencyConvertError(
                                    posting.meta or {},
                                    f"No price found for pricing {source_currency} in {target_currency} on {entry.date}",
                                    entry
                                ))
                                new_postings.append(posting)
                            else:
                                # Use inverse
                                exchange_rate = Decimal(1) / inverse_price_info[1]
                                new_price = Amount(exchange_rate, target_currency)
                                new_meta = dict(posting.meta) if posting.meta else {}
                                new_meta.pop(AT_TODAY_PRICE_METADATA_KEY, None)
                                new_posting = Posting(
                                    account=posting.account,
                                    units=posting.units,
                                    cost=posting.cost,
                                    price=new_price,
                                    flag=posting.flag,
                                    meta=new_meta if new_meta else None
                                )
                                new_postings.append(new_posting)
                                transaction_modified = True
                        else:
                            exchange_rate = price_info[1]
                            new_price = Amount(exchange_rate, target_currency)
                            new_meta = dict(posting.meta) if posting.meta else {}
                            new_meta.pop(AT_TODAY_PRICE_METADATA_KEY, None)
                            new_posting = Posting(
                                account=posting.account,
                                units=posting.units,
                                cost=posting.cost,
                                price=new_price,
                                flag=posting.flag,
                                meta=new_meta if new_meta else None
                            )
                            new_postings.append(new_posting)
                            transaction_modified = True
                else:
                    # No conversion or pricing needed, keep original posting
                    new_postings.append(posting)
            
            if transaction_modified:
                # Create new transaction with modified postings
                new_transaction = Transaction(
                    meta=entry.meta,
                    date=entry.date,
                    flag=entry.flag,
                    payee=entry.payee,
                    narration=entry.narration,
                    tags=entry.tags,
                    links=entry.links,
                    postings=new_postings
                )
                new_entries.append(new_transaction)
            else:
                # No changes, keep original transaction
                new_entries.append(entry)
        else:
            # Not a transaction, keep as-is
            new_entries.append(entry)
    
    return new_entries, errors
