"""This module automatically inserts Open directives for accounts not opened (at
the date of the first entry) and automatically removes open directives for
unused accounts. This can be used as a convenience for doing demos, or when
setting up your initial transactions, as an intermediate step.
"""

__copyright__ = "Copyright (C) 2014-2017, 2022, 2024  Martin Blais"
__license__ = "GNU GPLv2"

import ast
import collections
import re
from beancount.core import data
from beancount.core import getters

__plugins__ = ("auto_insert_open",)


AutoInsertOpenWarning = collections.namedtuple(
    "AutoInsertOpenWarning", "source message entry"
)


def auto_insert_open(entries, options_map, config_str=None):
    """Insert Open directives for accounts not opened.

    Open directives are inserted at the date of the first entry. Open directives
    for unused accounts are removed.

    Args:
      entries: A list of directives.
      unused_options_map: A parser options dict.
    Returns:
      A list of entries, possibly with more Open entries than before, and a
      list of errors.
    """
    opened_accounts = {entry.account for entry in entries if isinstance(entry, data.Open)}

    config = ast.literal_eval(config_str or "{}")
    ignored_regex = config.get("ignore_regex", None)

    errors = []
    new_entries = []
    auto_inserted_accounts = []
    accounts_first, _ = getters.get_accounts_use_map(entries)
    for index, (account, date_first_used) in enumerate(sorted(accounts_first.items())):
        if account not in opened_accounts:
            meta = data.new_metadata("<auto_accounts>", index)
            meta['auto_accounts'] = True
            new_entries.append(data.Open(meta, date_first_used, account, None, None))

            if not (ignored_regex and re.match(ignored_regex, account)):
                auto_inserted_accounts.append(account)

    # Create warnings for auto-inserted accounts
    if auto_inserted_accounts:        
        # Create a warning entry
        meta = data.new_metadata("<auto_insert_open>", 0)
        # Escape accounts because Fava's regex parsing breaks message in the error view otherwise
        escaped_accounts = ['- ' + account.replace(":", "/") for account in auto_inserted_accounts]
        warning = AutoInsertOpenWarning(
            meta,
            f"Auto-inserted Open directives for {len(auto_inserted_accounts)} accounts:\n" +
            f"{'\n'.join(escaped_accounts[:10])}" +
            (f"\n... ({len(escaped_accounts) - 10} more)" if len(escaped_accounts) > 10 else ""),
            None
        )
        errors.append(warning)

    if new_entries:
        new_entries.extend(entries)
        new_entries.sort(key=data.entry_sortkey)
    else:
        new_entries = entries

    return new_entries, errors
