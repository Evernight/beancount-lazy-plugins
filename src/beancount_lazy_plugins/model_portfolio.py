"""A Beancount plugin that generates model portfolio purchase transactions.

Reads 'custom "model-portfolio" "generate"' directives and generates periodic
purchase transactions based on a distribution spec, using the beancount price
map to look up commodity prices at each transaction date.

Usage in ledger:
    plugin "beancount_lazy_plugins.model_portfolio"

Example directive:
    2020-01-01 custom "model-portfolio" "generate"
      distribution: "[
        ('Assets:Portfolio:VWRP', 'VWRP', 0.8)
        ('Assets:Portfolio:BNDW', 'BNDW', 0.2)
      ]"
      time: "2 years / 2 months"
      type: "simple"
      source_account: "Assets:Investment:Cash"
      amount: "2000 USD"
      description: "Generated transaction for model portfolio"
      addTags: "#model_portfolio, #virtual"
"""

import ast
import collections
import datetime
import re
from decimal import Decimal, ROUND_HALF_EVEN

from dateutil.relativedelta import relativedelta

from beancount.core import data, prices
from beancount.core.amount import Amount
from beancount.core.data import Posting, Transaction
from beancount.core.position import CostSpec

__plugins__ = ["model_portfolio"]

ModelPortfolioError = collections.namedtuple(
    "ModelPortfolioError", "source message entry"
)

CUSTOM_TYPE = "model-portfolio"

# Parses time specs like "2 years / 2 months" or "6 months / 1 month".
# Format: [x period] [/ [m] step]
RE_TIMESPEC = re.compile(
    r"^\s*([0-9]+(?=[\sa-zA-Z]+))?"
    r"\s*([^-/\s]+)?"
    r"\s*(?:\/\s*([0-9]+(?=[\sa-zA-Z])(?!\s*$))?\s*([^-/\s]+)?\s*)?$"
)

_PERIOD_MAP = {
    "day": relativedelta(days=1),
    "days": relativedelta(days=1),
    "week": relativedelta(weeks=1),
    "weeks": relativedelta(weeks=1),
    "month": relativedelta(months=1),
    "months": relativedelta(months=1),
    "year": relativedelta(years=1),
    "years": relativedelta(years=1),
}


def _parse_period(token):
    token = token.strip().lower()
    if token in _PERIOD_MAP:
        return _PERIOD_MAP[token]
    try:
        return relativedelta(days=int(token))
    except ValueError:
        raise ValueError(f"Unknown period token: {token!r}")


def parse_timespec(spec, start_date):
    """Parse a time spec string and return a list of dates.

    Format: '[x period] [/ [m] step]'
    Example: '2 years / 2 months'

    Generates dates: start_date, start_date+step, start_date+2*step, …
    stopping when the date reaches start_date+duration or exceeds today.

    Args:
        spec: Time specification string.
        start_date: The initial date (datetime.date).
    Returns:
        A list of datetime.date objects.
    """
    m = RE_TIMESPEC.match(spec.strip())
    if not m:
        raise ValueError(f"Cannot parse time spec: {spec!r}")

    dur_mult = int(m.group(1)) if m.group(1) else 1
    dur_unit = m.group(2) if m.group(2) else "month"
    step_mult = int(m.group(3)) if m.group(3) else 1
    step_unit = m.group(4) if m.group(4) else dur_unit

    duration = _parse_period(dur_unit) * dur_mult
    step = _parse_period(step_unit) * step_mult

    end_date = start_date + duration
    today = datetime.date.today()

    dates = []
    i = 0
    while True:
        date = start_date + step * i
        if date >= end_date or date > today:
            break
        dates.append(date)
        i += 1

    return dates


def parse_tags(tag_str):
    """Parse a tag string like '#model_portfolio, #virtual' into a frozenset."""
    tags = set()
    for part in tag_str.split(","):
        part = part.strip().lstrip("#").strip()
        if part:
            tags.add(part)
    return frozenset(tags)


def parse_amount(amount_str):
    """Parse '2000 USD' into (Decimal('2000'), 'USD')."""
    parts = amount_str.strip().split()
    if len(parts) != 2:
        raise ValueError(f"Cannot parse amount: {amount_str!r}")
    return Decimal(parts[0]), parts[1]


def model_portfolio(entries, options_map, config_str=None):
    """Generate model portfolio purchase transactions.

    Args:
        entries: A list of directives.
        options_map: A parser options dict.
        config_str: Unused configuration string.
    Returns:
        A tuple of (entries, errors).
    """
    errors = []
    price_map = prices.build_price_map(entries)

    new_entries = []
    generated = []

    for entry in entries:
        if not (isinstance(entry, data.Custom) and entry.type == CUSTOM_TYPE):
            new_entries.append(entry)
            continue

        if not entry.values or entry.values[0].value != "generate":
            new_entries.append(entry)
            continue

        meta = entry.meta

        try:
            distribution_str = meta.get("distribution", "")
            distribution = ast.literal_eval(distribution_str)
            time_spec = meta["time"]
            source_account = meta["source_account"]
            amount_str = meta["amount"]
            description = meta.get("description", "Model portfolio purchase")
            tags = parse_tags(meta.get("addTags", ""))

            total_amount, base_currency = parse_amount(amount_str)
            dates = parse_timespec(time_spec, entry.date)

            for date in dates:
                postings = []
                has_error = False

                for (account, commodity, pct) in distribution:
                    asset_amount = total_amount * Decimal(str(pct))

                    price_info = prices.get_price(
                        price_map, (commodity, base_currency), date
                    )
                    if price_info[1] is None:
                        errors.append(ModelPortfolioError(
                            meta,
                            f"No price found for {commodity}/{base_currency} on {date}",
                            entry,
                        ))
                        has_error = True
                        break

                    price_per_unit = price_info[1]
                    units = (asset_amount / price_per_unit).quantize(
                        Decimal("0.00000001"), rounding=ROUND_HALF_EVEN
                    )

                    cost_spec = CostSpec(
                        number_per=price_per_unit,
                        number_total=None,
                        currency=base_currency,
                        date=None,
                        label=None,
                        merge=False,
                    )

                    postings.append(Posting(
                        account=account,
                        units=Amount(units, commodity),
                        cost=cost_spec,
                        price=None,
                        flag=None,
                        meta={},
                    ))

                if has_error:
                    continue

                postings.append(Posting(
                    account=source_account,
                    units=Amount(-total_amount, base_currency),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={},
                ))

                tx_meta = data.new_metadata("<model_portfolio>", 0)
                tx_meta["generated_by"] = "model_portfolio"

                tx = Transaction(
                    meta=tx_meta,
                    date=date,
                    flag="*",
                    payee=None,
                    narration=description,
                    tags=tags,
                    links=frozenset(),
                    postings=postings,
                )
                generated.append(tx)

        except Exception as e:
            errors.append(ModelPortfolioError(
                meta,
                f"Error processing model-portfolio directive: {e}",
                entry,
            ))

    new_entries.extend(generated)
    new_entries.sort(key=data.entry_sortkey)

    return new_entries, errors
