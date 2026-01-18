"""Automatic padding of gaps between entries."""

__copyright__ = "Copyright (C) 2013-2017, 2020, 2024  Martin Blais"
__license__ = "GNU GPLv2"

import ast
import math
import pprint
import re
from dataclasses import dataclass
from typing import NamedTuple

from beancount.core import account
from beancount.core import amount
from beancount.core import data
from beancount.core import flags
from beancount.core import inventory
from beancount.core import position
from beancount.core import realization
from beancount.ops import balance
from beancount.utils import misc_utils

__plugins__ = ["pad_extended"]


DEFAULT_DEFAULT_PAD_ACCOUNT_CONFIG = [
    (r"^.*$", "Expenses:Unattributed:{name}", "Income:Unattributed:{name}"),
]

@dataclass
class RegexToPadAccountMapping:
    regex: re.Pattern
    pad_account: str | None = None
    pad_account_expenses: str | None = None
    pad_account_income: str | None = None

class PadError(NamedTuple):
    """Represents an error encountered during padding."""

    source: data.Meta
    message: str
    entry: data.Pad


def is_pad_entry(entry, config):
    if isinstance(entry, data.Pad):
        return config.get('handle_default_pad_directives', False)
    return isinstance(entry, data.Custom) and entry.type == "pad-ext"

def get_padded_account(pad_entry):
    if type(pad_entry) == data.Pad:
        return pad_entry.account
    return pad_entry.values[0].value

def get_source_account(pad_entry, diff_position, default_pad_account_config, default_pad_acount_cache):
    """
    Get the source account for a pad entry in the following order of precedence:
    1. The account specified in the pad entry metadata (pad_account)
    2. The account specified in pad-ext-config statements of matching regex
    2. The account specified in the default pad account configuration of matching regex
    """
    if type(pad_entry) == data.Pad:
        # Supports only direct specification of source account in Pad directive
        return pad_entry.source_account

    # Otherwise going down the specificity chain
    if pad_entry.meta.get('pad_account'):
        return pad_entry.meta.get('pad_account')

    pad_entry_account = pad_entry.values[0].value

    position_sign = math.copysign(1, diff_position.units.number)
    key = (pad_entry_account, position_sign)
    if key in default_pad_acount_cache:
        return default_pad_acount_cache[key]

    parts = pad_entry_account.split(':')
    account_type = parts[0]
    name = ':'.join(parts[1:])

    # default_pad_account_config is sorted in decreasing specificity order
    for mapping in default_pad_account_config:        
        if mapping.regex.match(pad_entry_account):
            if mapping.pad_account_expenses and mapping.pad_account_income:
                if position_sign > 0:
                    res = mapping.pad_account_income.format(type=account_type, name=name)
                else:
                    res = mapping.pad_account_expenses.format(type=account_type, name=name)
            elif mapping.pad_account:
                res = mapping.pad_account.format(type=account_type, name=name)
            else:
                raise ValueError(f"Invalid default pad account configuration: {mapping}")

            default_pad_acount_cache[key] = res
            return res
    return None

def get_directives_defined_config(entries, pad_errors):
    parsed_config = []
    pad_config_entries = [
        entry
        for entry in entries
        if isinstance(entry, data.Custom) and entry.type == "pad-ext-config"
    ]
    for entry in reversed(pad_config_entries):
        account_regex = entry.meta.get("account_regex")
        if not account_regex:
            pad_errors.append(
                PadError(
                    entry.meta,
                    "account_regex is required in config entry",
                    entry,
                )
            )
            continue
        compiled_account_regex = None
        try:
            compiled_account_regex = re.compile(account_regex)
        except re.error as e:
            pad_errors.append(
                PadError(
                    entry.meta,
                    f"Invalid account_regex: {e}",
                    entry,
                )
            )
            continue
        expenses_account = entry.meta.get("pad_account_expenses")
        income_account = entry.meta.get("pad_account_income")
        pad_account = entry.meta.get("pad_account")
        if expenses_account and income_account:
            parsed_config.append(
                RegexToPadAccountMapping(compiled_account_regex, pad_account_income=income_account, pad_account_expenses=expenses_account)
            )
        elif pad_account:
            parsed_config.append(
                RegexToPadAccountMapping(compiled_account_regex, pad_account=pad_account)
            )
        else:
            pad_errors.append(
                PadError(
                    entry.meta,
                    "pad-ext-config requires account_regex and (pad_account or pad_account_expenses and pad_account_income)",
                    entry,
                )
            )
            continue        
    return parsed_config


def parse_pad_account_item(item):
    if len(item) > 4:
        raise ValueError(
            f"Invalid default pad account configuration: {item}. Should be (regex, source_account) or (regex, source_account_positive, source_account_negative) or (regex, source_account_positive, source_account_negative, initial_source_account)"
        )
    pattern = re.compile(item[0])
    if len(item) == 2:
        return RegexToPadAccountMapping(pattern, pad_account=item[1])
    elif len(item) >= 3:
        return RegexToPadAccountMapping(pattern, pad_account_income=item[1], pad_account_expenses=item[2])


def pad_extended(entries, options_map, config_str=None):
    """Insert transaction entries for to fulfill a subsequent balance check.

    This is an extended version of the pad plugin supplied with Beancount (beancount.ops.pad).
    See original plugin code and documentation for more details. Only differences will be documented here.

    Args:
      entries: A list of directives.
      options_map: A parser options dict.
      config_str: Optional configuration string.
    Returns:
      A new list of directives, with Pad entries inserted, and a list of new
      errors produced.
    """
    pad_errors = []

    config = {}
    if config_str:
        try:
            config = ast.literal_eval(config_str)
        except (ValueError, SyntaxError) as e:
            pad_errors.append(PadError(
                source=None,
                message=f"Invalid configuration string: {e}",
                entry=None
            ))
            return entries, pad_errors

    default_pad_account_config = []
    # Reverse for convenient checking later
    for item in reversed(config.get('default_pad_account', DEFAULT_DEFAULT_PAD_ACCOUNT_CONFIG)):
        default_pad_account_config.append(parse_pad_account_item(item))

    directives_account_config = get_directives_defined_config(entries, pad_errors)
    if pad_errors:
        return entries, pad_errors

    default_pad_account_config = directives_account_config + default_pad_account_config
    default_pad_acount_cache = {}

    # Find all the pad entries and group them by account.
    pads = [e for e in entries if is_pad_entry(e, config)]
    pad_dict = misc_utils.groupby(lambda x: get_padded_account(x), pads)

    # Partially realize the postings, so we can iterate them by account.
    by_account = realization.postings_by_account(entries)

    # A dict of pad -> list of entries to be inserted.
    new_entries = {id(pad): [] for pad in pads}

    # Process each account that has a padding group.
    for account_, pad_list in sorted(pad_dict.items()):
        # Last encountered / currency active pad entry.
        active_pad = None

        # Gather all the postings for the account and its children.
        postings = []
        is_child = account.parent_matcher(account_)
        for item_account, item_postings in by_account.items():
            if is_child(item_account):
                postings.extend(item_postings)
        postings.sort(key=data.posting_sortkey)

        # A set of currencies already padded so far in this account.
        padded_lots = set()

        pad_balance = inventory.Inventory()
        for entry in postings:
            assert not isinstance(entry, data.Posting)
            if isinstance(entry, data.TxnPosting):
                # This is a transaction; update the running balance for this
                # account.
                pad_balance.add_position(entry.posting)

            elif is_pad_entry(entry, config):
                pad_entry_account = get_padded_account(entry)
                if pad_entry_account == account_:
                    # Mark this newly encountered pad as active and allow all lots
                    # to be padded heretofore.
                    active_pad = entry
                    padded_lots = set()

            elif isinstance(entry, data.Balance):
                check_amount = entry.amount

                # Compare the current balance amount to the expected one from
                # the check entry. IMPORTANT: You need to understand that this
                # does not check a single position, but rather checks that the
                # total amount for a particular currency (which itself is
                # distinct from the cost).
                balance_amount = pad_balance.get_currency_units(check_amount.currency)
                diff_amount = amount.sub(balance_amount, check_amount)

                # Use the specified tolerance or automatically infer it.
                tolerance = balance.get_balance_tolerance(entry, options_map)

                if abs(diff_amount.number) > tolerance:
                    # The check fails; we need to pad.

                    # Pad only if pad entry is active and we haven't already
                    # padded that lot since it was last encountered.
                    if active_pad and (check_amount.currency not in padded_lots):
                        # Note: we decide that it's an error to try to pad
                        # positions at cost; we check here that all the existing
                        # positions with that currency have no cost.
                        positions = [
                            pos
                            for pos in pad_balance.get_positions()
                            if pos.units.currency == check_amount.currency
                        ]
                        for position_ in positions:
                            if position_.cost is not None:
                                pad_errors.append(
                                    PadError(
                                        entry.meta,
                                        (
                                            "Attempt to pad an entry with cost for "
                                            "balance: {}".format(pad_balance)
                                        ),
                                        active_pad,
                                    )
                                )

                        # Thus our padding lot is without cost by default.
                        diff_position = position.Position.from_amounts(
                            amount.Amount(
                                check_amount.number - balance_amount.number,
                                check_amount.currency,
                            )
                        )

                        # Synthesize a new transaction entry for the difference.
                        narration = (
                            "(Padding inserted for Balance of {} for difference {})"
                        ).format(check_amount, diff_position)
                        new_entry = data.Transaction(
                            active_pad.meta.copy(),
                            active_pad.date,
                            flags.FLAG_PADDING,
                            None,
                            narration,
                            data.EMPTY_SET,
                            data.EMPTY_SET,
                            [],
                        )

                        pad_entry_account = get_padded_account(active_pad)
                        new_entry.postings.append(
                            data.Posting(
                                pad_entry_account,
                                diff_position.units,
                                diff_position.cost,
                                None,
                                None,
                                entry.meta,
                            )
                        )
                        source_account = get_source_account(
                            active_pad,
                            diff_position,
                            default_pad_account_config, 
                            default_pad_acount_cache
                        )

                        neg_diff_position = -diff_position
                        new_entry.postings.append(
                            data.Posting(
                                source_account,
                                neg_diff_position.units,
                                neg_diff_position.cost,
                                None,
                                None,
                                entry.meta,
                            )
                        )

                        # Save it for later insertion after the active pad.
                        new_entries[id(active_pad)].append(new_entry)

                        # Fixup the running balance.
                        pos, _ = pad_balance.add_position(diff_position)
                        if pos is not None and pos.is_negative_at_cost():
                            raise ValueError(
                                "Position held at cost goes negative: {}".format(pos)
                            )

                # Mark this lot as padded. Further checks should not pad this lot.
                padded_lots.add(check_amount.currency)

    # Insert the newly created entries right after the pad entries that created them.
    padded_entries = []
    for entry in entries:
        padded_entries.append(entry)
        if is_pad_entry(entry, config):
            entry_list = new_entries[id(entry)]
            if entry_list:
                padded_entries.extend(entry_list)
            else:
                # Generate errors on unused pad entries.
                if config.get('generate_errors_on_unused_pad_entries', False):
                    pad_errors.append(PadError(entry.meta, "Unused Pad entry", entry))
                else:
                    # Skip the pad entry
                    continue

    return padded_entries, pad_errors
