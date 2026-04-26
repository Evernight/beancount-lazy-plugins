"""
Tests for the model_portfolio plugin.
"""

from decimal import Decimal
from datetime import date

import pytest
from beancount import loader
from beancount.core.data import Custom, Price, Transaction
from beancount.core.amount import Amount

from beancount_lazy_plugins.model_portfolio import model_portfolio, parse_timespec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(ledger_text):
    """Load a ledger string (no plugin) and run the model_portfolio plugin on it."""
    entries, errors, options_map = loader.load_string(ledger_text)
    return model_portfolio(entries, options_map)


# ---------------------------------------------------------------------------
# parse_timespec unit tests
# ---------------------------------------------------------------------------

def test_parse_timespec_generates_correct_dates():
    """'2 months / 1 month' from 2020-01-01 → [2020-01-01, 2020-02-01]."""
    dates = parse_timespec("2 months / 1 month", date(2020, 1, 1))
    assert dates == [date(2020, 1, 1), date(2020, 2, 1)]


def test_parse_timespec_respects_duration():
    """Step dates beyond the duration are excluded."""
    dates = parse_timespec("1 month / 1 month", date(2020, 1, 1))
    assert dates == [date(2020, 1, 1)]


def test_parse_timespec_future_dates_excluded():
    """Dates beyond today are not generated."""
    # Start far in the future — should produce no dates.
    dates = parse_timespec("2 years / 1 month", date(2099, 1, 1))
    assert dates == []


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

LEDGER_BASIC = """
2020-01-01 open Assets:Portfolio:VWRP
2020-01-01 open Assets:Portfolio:BNDW
2020-01-01 open Assets:Investment:Cash

2020-01-01 price VWRP  100.00 USD
2020-01-01 price BNDW   50.00 USD

2020-01-01 custom "model-portfolio" "generate"
  distribution: "[('Assets:Portfolio:VWRP', 'VWRP', 0.8), ('Assets:Portfolio:BNDW', 'BNDW', 0.2)]"
  time: "1 month / 1 month"
  type: "simple"
  source_account: "Assets:Investment:Cash"
  amount: "2000 USD"
  description: "Test purchase"
  addTags: "#test_tag"
"""


def test_generates_one_transaction():
    """A 1-month window with 1-month step produces exactly one transaction."""
    entries, errors = _run(LEDGER_BASIC)
    txns = [e for e in entries if isinstance(e, Transaction)]
    assert len(txns) == 1


def test_transaction_date():
    """Generated transaction date matches the directive date."""
    entries, errors = _run(LEDGER_BASIC)
    txns = [e for e in entries if isinstance(e, Transaction)]
    assert txns[0].date == date(2020, 1, 1)


def test_transaction_narration_and_tags():
    """Narration and tags are correctly set on the generated transaction."""
    entries, errors = _run(LEDGER_BASIC)
    txns = [e for e in entries if isinstance(e, Transaction)]
    tx = txns[0]
    assert tx.narration == "Test purchase"
    assert "test_tag" in tx.tags


def test_posting_units_vwrp():
    """VWRP units = 1600 / 100.00 = 16.00000000."""
    entries, errors = _run(LEDGER_BASIC)
    txns = [e for e in entries if isinstance(e, Transaction)]
    tx = txns[0]
    vwrp = next(p for p in tx.postings if p.account == "Assets:Portfolio:VWRP")
    assert vwrp.units.currency == "VWRP"
    assert vwrp.units.number == Decimal("16.00000000")


def test_posting_units_bndw():
    """BNDW units = 400 / 50.00 = 8.00000000."""
    entries, errors = _run(LEDGER_BASIC)
    txns = [e for e in entries if isinstance(e, Transaction)]
    tx = txns[0]
    bndw = next(p for p in tx.postings if p.account == "Assets:Portfolio:BNDW")
    assert bndw.units.currency == "BNDW"
    assert bndw.units.number == Decimal("8.00000000")


def test_posting_cost_basis():
    """Asset postings carry {price USD} cost basis."""
    entries, errors = _run(LEDGER_BASIC)
    txns = [e for e in entries if isinstance(e, Transaction)]
    tx = txns[0]
    vwrp = next(p for p in tx.postings if p.account == "Assets:Portfolio:VWRP")
    assert vwrp.cost is not None
    assert vwrp.cost.number_per == Decimal("100.00")
    assert vwrp.cost.currency == "USD"


def test_source_account_posting():
    """Source account is debited by the full amount."""
    entries, errors = _run(LEDGER_BASIC)
    txns = [e for e in entries if isinstance(e, Transaction)]
    tx = txns[0]
    cash = next(p for p in tx.postings if p.account == "Assets:Investment:Cash")
    assert cash.units == Amount(Decimal("-2000"), "USD")


def test_custom_directive_removed():
    """The custom directive is consumed and does not appear in output."""
    entries, errors = _run(LEDGER_BASIC)
    customs = [e for e in entries if isinstance(e, Custom)]
    assert len(customs) == 0


def test_no_plugin_errors():
    """Basic ledger produces no ModelPortfolioError entries."""
    entries, errors = _run(LEDGER_BASIC)
    assert errors == []


# ---------------------------------------------------------------------------
# Multi-period test
# ---------------------------------------------------------------------------

LEDGER_MULTI = """
2019-01-01 open Assets:Portfolio:VWRP
2019-01-01 open Assets:Investment:Cash

2019-01-01 price VWRP  100.00 USD

2019-01-01 custom "model-portfolio" "generate"
  distribution: "[('Assets:Portfolio:VWRP', 'VWRP', 1.0)]"
  time: "3 months / 1 month"
  type: "simple"
  source_account: "Assets:Investment:Cash"
  amount: "1000 USD"
  description: "Monthly buy"
  addTags: ""
"""


def test_multi_period_transaction_count():
    """'3 months / 1 month' produces 3 transactions."""
    entries, errors = _run(LEDGER_MULTI)
    txns = [e for e in entries if isinstance(e, Transaction)]
    assert len(txns) == 3


def test_multi_period_dates():
    """Transactions are on the 1st of Jan, Feb, Mar 2019."""
    entries, errors = _run(LEDGER_MULTI)
    txns = sorted(
        [e for e in entries if isinstance(e, Transaction)],
        key=lambda t: t.date,
    )
    assert [t.date for t in txns] == [
        date(2019, 1, 1),
        date(2019, 2, 1),
        date(2019, 3, 1),
    ]


# ---------------------------------------------------------------------------
# Missing price → error
# ---------------------------------------------------------------------------

LEDGER_NO_PRICE = """
2020-01-01 open Assets:Portfolio:VWRP
2020-01-01 open Assets:Investment:Cash

2020-01-01 custom "model-portfolio" "generate"
  distribution: "[('Assets:Portfolio:VWRP', 'VWRP', 1.0)]"
  time: "1 month / 1 month"
  type: "simple"
  source_account: "Assets:Investment:Cash"
  amount: "1000 USD"
  description: "Buy without price"
  addTags: ""
"""


def test_missing_price_emits_error():
    """When no price is available, an error is emitted."""
    entries, errors = _run(LEDGER_NO_PRICE)
    assert len(errors) == 1
    assert "No price found" in errors[0].message
    assert "VWRP" in errors[0].message


def test_missing_price_skips_transaction():
    """When no price is available, no transaction is generated."""
    entries, errors = _run(LEDGER_NO_PRICE)
    txns = [e for e in entries if isinstance(e, Transaction)]
    assert len(txns) == 0
