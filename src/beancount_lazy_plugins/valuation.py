"""
A Beancount plugin that allows to specify total investment account value over 
time and creates an underlying fictional commodity which price is set up to 
match total value of the account over time.

All incoming and outcoming transactions in and from account are converted into
transactions buying and selling this commodity at calculated price at the date.
"""

import collections

from beancount.core.data import Transaction
from beancount.core.data import Custom
from beancount.core.data import Price
from beancount.core.data import Amount
from beancount.core.data import Posting
from beancount.core.data import Commodity
from beancount.core.data import Balance
from beancount.core.position import CostSpec
from beancount.core.number import MISSING
import decimal
from decimal import Decimal

# Note: do not use from beancount.parser import booking !
# There's a non-obvious
from beancount.parser import booking_full

def round_down(value, decimals):
    with decimal.localcontext() as ctx:
        d = decimal.Decimal(value)
        ctx.rounding = decimal.ROUND_DOWN
        return round(d, decimals)
    
def round_up(value, decimals):
    with decimal.localcontext() as ctx:
        d = decimal.Decimal(value)
        ctx.rounding = decimal.ROUND_UP
        return round(d, decimals)

__plugins__ = ['valuation']

MAPPED_CURRENCY_PRECISION = 7

def valuation(entries, options_map, config_str=None):
    # Configuration defined via valuation-config statement is a dictionary
    # where key is the account name and value is the name of the synthetical 
    # currency to be used
    account_mapping = {}

    commodities_present = set()
    commodities = []
    prices = []
    plugin_errors = []
    new_entries = []
    modified_transactions = []

    # We'll track balances of the relevant accounts here
    balances = collections.defaultdict(Decimal)
    # and will keep the last calculated price
    last_price = {}

    for entry in entries:
        if isinstance(entry, Custom) and entry.type == 'valuation-config':
            config_str = entry.values[0].value.strip()
            if config_str and config_str:
                account_mapping = eval(config_str, {}, {})
                if not isinstance(account_mapping, dict):
                    raise RuntimeError("Invalid configuration")
        elif isinstance(entry, Transaction):
            transaction_modified = False

            # Replace postings if the account is in the plugin configuration
            new_postings = []
            for posting in entry.postings:
                if posting.account in account_mapping:
                    transaction_modified = True
                    mapped_currency, pnl_account = account_mapping[posting.account]

                    last_valuation_price = last_price.get(mapped_currency, Decimal(1.0))
                    total_in_mapped_currency = posting.units.number / last_valuation_price

                    if posting.units.number > 0:
                        # Cash in-flow into account, "buy" at last valuation price
                        modified_posting = Posting(
                            posting.account,
                            Amount(round_up(total_in_mapped_currency, MAPPED_CURRENCY_PRECISION), mapped_currency), 
                            cost=CostSpec(last_valuation_price, None, posting.units.currency, entry.date, None, False),
                            price=None,
                            flag=posting.flag,
                            meta=posting.meta)
                    else:
                        modified_posting = Posting(
                            posting.account,
                            Amount(round_down(total_in_mapped_currency, MAPPED_CURRENCY_PRECISION), mapped_currency), 
                            cost=CostSpec(MISSING, None, posting.units.currency, None, None, False),
                            price=Amount(last_valuation_price, posting.units.currency),
                            flag=posting.flag,
                            meta=posting.meta)
                        
                        # Also add automatic balancing with PnL account
                        new_postings.append(
                            Posting(
                              pnl_account, 
                              None,
                              cost=None,
                              price=posting.price,
                              flag=posting.flag,
                              meta=posting.meta)
                        )

                    if posting.price:
                        # Specifying cost and price together all in different currencies doesn't work
                        # Instead, add a balancing "conversion" to original currency, in addition to mapped_currency 
                        # at cost above
                        new_postings.append(
                            Posting(
                              posting.account, 
                              Amount(posting.units.number, posting.units.currency), 
                              cost=None,
                              price=posting.price,
                              flag=posting.flag,
                              meta=posting.meta)
                        )
                        new_postings.append(
                            Posting(
                              posting.account, 
                              Amount(-posting.units.number, posting.units.currency), 
                              cost=None,
                              price=None,
                              flag=posting.flag,
                              meta=posting.meta)
                        )

                    new_postings.append(modified_posting)
                    balances[posting.account] += total_in_mapped_currency
                else:
                    new_postings.append(posting)

            if transaction_modified:
                # Same old transaction, updated postings
                transaction = Transaction(
                    entry.meta,
                    entry.date,
                    flag=entry.flag,
                    payee=entry.payee,
                    narration=entry.narration,
                    tags=entry.tags,
                    links=entry.links,
                    postings=new_postings)
                modified_transactions.append(transaction)
            else:
                new_entries.append(entry)
        elif isinstance(entry, Balance) and entry.account in account_mapping:
            mapped_currency, pnl_account = account_mapping[entry.account]
            assert entry.account not in balances, "a single balance statement should be before any valuation assertion"
            
            price = Price(
                entry.meta, entry.date, mapped_currency,
                Amount(Decimal(1.0), valuation_amount.currency)
            )
            last_price[mapped_currency] = Decimal(1.0)
            balances[entry.account] = entry.amount.number

            prices.append(price)
        elif isinstance(entry, Custom) and entry.type == 'valuation':
            account, valuation_amount = entry.values
            account = account.value

            valuation_currency, pnl_account = account_mapping[account]
            valuation_amount = valuation_amount.value
            last_balance = balances[account]
            
            price = Price(
                entry.meta, entry.date, valuation_currency, 
                Amount(valuation_amount.number/last_balance, valuation_amount.currency)
            )
            last_price[valuation_currency] = Decimal(price.amount.number)

            prices.append(price)

            new_entries.append(entry)
        elif isinstance(entry, Commodity):
            # Just keep track of all the commodities defined in the ledger
            commodities_present.add(entry.currency)
            new_entries.append(entry)
        else:
            # No-op on all other entries
            new_entries.append(entry)

    # If the fictional synthesized currency hasn't been defined by the user, 
    # define it automatically
    for account, (acc_currency, pnl_account) in account_mapping.items():
        if acc_currency not in commodities_present:
          commodity = Commodity(entry.meta, entry.date, acc_currency)
          commodities.append(commodity)

    # Call booking.book to automatically fill unspecified cost values for out-flows
    # TODO: if it's not called, MISSING values trigger error. Would it be possible to avoid these calls?
    booking_methods = collections.defaultdict(lambda: options_map["booking_method"])
    cost_processed_transactions, cost_processed_errors = booking_full.book(
        modified_transactions, options_map, booking_methods)

    return new_entries + commodities + prices + cost_processed_transactions, plugin_errors + cost_processed_errors
