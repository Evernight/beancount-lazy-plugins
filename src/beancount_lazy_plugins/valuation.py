"""
A Beancount plugin that allows to specify total investment account value over
time and creates an underlying fictional commodity which price is set up to
match total value of the account over time.

All incoming and outcoming transactions in and from account are converted into
transactions buying and selling this commodity at calculated price at the date.
"""

import collections
import copy
import decimal
from decimal import Decimal
import sys

from beancount.core.data import (
    Amount,
    Balance,
    Commodity,
    Custom,
    Posting,
    Price,
    Transaction,
    Open,
    Booking
)
from beancount.core.position import CostSpec, Cost
from beancount.core.number import MISSING

from beancount.parser import printer

# Note: do not use from beancount.parser import booking !!!
# There's a non-obvious bug while working with the beancount-import library:
# see "intercept_book" function
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


__plugins__ = ["valuation"]

MAPPED_CURRENCY_PRECISION = 7
EPSILON = 1e-9

TAG_TO_ADD = "valuation-applied"

ValuationPluginError = collections.namedtuple(
    "ValuationPluginError", "source message entry"
)


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

    account_mapping = {}
    # read config
    for entry in entries:
        if (
            isinstance(entry, Custom)
            and entry.type == "valuation"
            and entry.values[0].value == "config"
        ):
            account_mapping[entry.meta["account"]] = (
                entry.meta["currency"],
                entry.meta["pnlAccount"],
            )

    booking_methods = {}
    open_account_entries = {}
    for entry in entries:
        if isinstance(entry, Open) and entry.account in account_mapping:
            open_account_entries[entry.account] = entry
    for account in account_mapping.keys():
        if account not in open_account_entries:
            open_account_entries[account] = Open(
                entry.meta,
                entry.date,
                entry.account,
                account_mapping[account]['currency'],
                Booking.FIFO
            )
        booking_methods[account] = Booking.FIFO


    # We'll track balances of the relevant accounts here
    balances = collections.defaultdict(Decimal)
    # and will keep the last calculated price
    last_price = {}

    for entry in entries:
        if isinstance(entry, Transaction):
            transaction_modified = False

            # Replace postings if the account is in the plugin configuration
            new_postings = []
            for posting in entry.postings:
                if posting.account in account_mapping:
                    transaction_modified = True
                    mapped_currency, pnl_account = account_mapping[posting.account]

                    if mapped_currency in last_price:
                        last_valuation_price = last_price[mapped_currency]
                    else:
                        # There was no valuation operation before, set default mapped curency to equal value as currency
                        last_valuation_price = Decimal(1.0)
                        price = Price(
                            entry.meta,
                            entry.date,
                            mapped_currency,
                            Amount(Decimal(1.0), posting.units.currency),
                        )
                        prices.append(price)
                    total_in_mapped_currency = (
                        posting.units.number / last_valuation_price
                    )

                    if posting.units.number > 0:
                        # Cash in-flow into account, "buy" at last valuation price
                        modified_posting = Posting(
                            posting.account,
                            Amount(
                                round_up(
                                    total_in_mapped_currency, MAPPED_CURRENCY_PRECISION
                                ),
                                mapped_currency,
                            ),
                            cost=Cost(last_valuation_price, posting.units.currency, None, None),
                            price=None,
                            flag=posting.flag,
                            meta=posting.meta,
                        )
                    else:
                        # Cash out-flow, "sell" underlying currency
                        modified_posting = Posting(
                            posting.account,
                            Amount(
                                round_down(
                                    total_in_mapped_currency, MAPPED_CURRENCY_PRECISION
                                ),
                                mapped_currency,
                            ),
                            cost=CostSpec(MISSING, None, posting.units.currency, None, None, False),
                            # cost=None,
                            price=Amount(last_valuation_price, posting.units.currency),
                            flag=posting.flag,
                            meta=posting.meta,
                        )

                        # Also add automatic balancing with PnL account
                        new_postings.append(
                            Posting(
                                pnl_account,
                                None,
                                cost=None,
                                price=posting.price,
                                flag=posting.flag,
                                meta=posting.meta,
                            )
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
                                meta=posting.meta,
                            )
                        )
                        new_postings.append(
                            Posting(
                                posting.account,
                                Amount(-posting.units.number, posting.units.currency),
                                cost=None,
                                price=None,
                                flag=posting.flag,
                                meta=posting.meta,
                            )
                        )

                    new_postings.append(modified_posting)
                    balances[posting.account] += total_in_mapped_currency
                else:
                    new_postings.append(posting)

            if transaction_modified:
                new_tags = set(copy.deepcopy(entry.tags))
                new_tags.add(TAG_TO_ADD)
                # Same old transaction, updated postings
                transaction = Transaction(
                    entry.meta,
                    entry.date,
                    flag=entry.flag,
                    payee=entry.payee,
                    narration=entry.narration,
                    tags=new_tags,
                    links=entry.links,
                    postings=new_postings,
                )
                modified_transactions.append(transaction)
            else:
                new_entries.append(entry)
        elif isinstance(entry, Balance) and entry.account in account_mapping:
            mapped_currency, pnl_account = account_mapping[entry.account]
            assert entry.account not in balances, (
                "a single balance statement should be before any valuation assertion"
            )

            price = Price(
                entry.meta,
                entry.date,
                mapped_currency,
                Amount(Decimal(1.0), entry.amount.currency),
            )
            last_price[mapped_currency] = Decimal(1.0)
            balances[entry.account] = entry.amount.number

            prices.append(price)
        elif (
            isinstance(entry, Custom)
            and entry.type == "valuation"
            and entry.values[0].value != "config"
        ):
            account, valuation_amount = entry.values
            account = account.value

            if account not in account_mapping:
                plugin_errors.append(
                    ValuationPluginError(
                        entry.meta,
                        "Please add account mapping configuration with currency and PnL account"
                        + ' before using "valuation" operation. Refer to documentation and examples',
                        entry,
                    )
                )
                continue
            valuation_currency, pnl_account = account_mapping[account]
            valuation_amount = valuation_amount.value
            last_balance = balances[account]

            if abs(last_balance) < EPSILON:
                plugin_errors.append(
                    ValuationPluginError(
                        entry.meta,
                        'Operation "valuation" was called on an empty account. '
                        + "Please add some non-zero transactions into account or use pad+balance operations before"
                        + ' the first "valuation" opeartion',
                        entry,
                    )
                )
                continue

            price = Price(
                entry.meta,
                entry.date,
                valuation_currency,
                Amount(
                    valuation_amount.number / last_balance, valuation_amount.currency
                ),
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

    # print('\n\nmodified_transactions')
    # printer.print_entries(modified_transactions)
    # sys.stdout.flush()

    # print('booking_methods')
    # print(booking_methods)
    # sys.stdout.flush()

    # Call booking.book to automatically fill unspecified cost values for out-flows
    # If it's not called, MISSING values or other absent values trigger error.
    # TODO: Would it be possible to avoid these calls?
    cost_processed_transactions, cost_processed_errors = booking_full.book(
        list(open_account_entries.values()) + modified_transactions, options_map, booking_methods
    )

    # print('\n\ncost_processed_transactions')
    # printer.print_entries(cost_processed_transactions)
    # sys.stdout.flush()

    # print('\n\ncost_processed_errors')
    # printer.print_errors(cost_processed_errors)
    # sys.stdout.flush()

    return (
        new_entries + commodities + prices + \
              [e for e in cost_processed_transactions if isinstance(e, Transaction)],
        plugin_errors + cost_processed_errors,
    )
