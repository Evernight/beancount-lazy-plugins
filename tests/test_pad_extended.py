"""
Tests for the pad_extended plugin.
"""

import datetime
import unittest
from decimal import Decimal
from textwrap import dedent

from beancount.core import data, flags
from beancount.core.amount import Amount
from beancount.core.number import D
from beancount.loader import load_string


class TestPadExtended(unittest.TestCase):
    """Test cases for pad_extended plugin."""

    def load_from_string(self, text):
        entries, errors, options_map = load_string(dedent(text))
        return entries, errors, options_map

    def test_two_pads_same_account_initial_and_regular(self):
        """Test two pads for the same account: first uses pad_account_initial, second uses pad_account."""
        ledger = """
        option "plugin_processing_mode" "raw"
        plugin "beancount_lazy_plugins.pad_extended"
        plugin "beancount.ops.balance"

        2015-01-01 open Assets:Bank USD
        2015-01-01 open Equity:Opening-Balances USD
        2015-01-01 open Expenses:Unreconciled USD

        2015-01-01 custom "pad-ext" "config"
            account_regex: "Assets:Bank"
            pad_account: "Expenses:Unreconciled"
            pad_account_initial: "Equity:Opening-Balances"

        2015-01-01 custom "pad-ext" Assets:Bank

        2015-01-02 balance Assets:Bank 100 USD

        2015-01-03 custom "pad-ext" Assets:Bank

        2015-01-04 balance Assets:Bank 150 USD
        """
        entries, errors, options_map = self.load_from_string(ledger)

        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")

        # Find padding transactions (flag 'P')
        padding_txns = [
            e
            for e in entries
            if isinstance(e, data.Transaction) and e.flag == flags.FLAG_PADDING
        ]
        self.assertEqual(
            len(padding_txns),
            2,
            f"Expected 2 padding transactions, got {len(padding_txns)}",
        )

        # First padding: 100 USD to Assets:Bank from Equity:Opening-Balances (initial)
        txn1 = padding_txns[0]
        self.assertEqual(txn1.date, datetime.date(2015, 1, 1))
        source_accounts = [
            p.account for p in txn1.postings if p.account != "Assets:Bank"
        ]
        self.assertEqual(
            source_accounts,
            ["Equity:Opening-Balances"],
            "First balance should use pad_account_initial (Equity:Opening-Balances)",
        )
        amounts = {p.account: p.units for p in txn1.postings}
        self.assertEqual(amounts["Assets:Bank"], Amount(D("100"), "USD"))
        self.assertEqual(amounts["Equity:Opening-Balances"], Amount(D("-100"), "USD"))

        # Second padding: 50 USD to Assets:Bank from Expenses:Unreconciled (regular)
        txn2 = padding_txns[1]
        self.assertEqual(txn2.date, datetime.date(2015, 1, 3))
        source_accounts = [
            p.account for p in txn2.postings if p.account != "Assets:Bank"
        ]
        self.assertEqual(
            source_accounts,
            ["Expenses:Unreconciled"],
            "Second balance should use pad_account (Expenses:Unreconciled)",
        )
        amounts = {p.account: p.units for p in txn2.postings}
        self.assertEqual(amounts["Assets:Bank"], Amount(D("50"), "USD"))
        self.assertEqual(amounts["Expenses:Unreconciled"], Amount(D("-50"), "USD"))

    def test_pad_and_pad_ext_both_handled(self):
        """Test pad_extended handles both standard Pad and pad-ext: pad, balance,
        pad-ext, balance. First balance uses Pad (source_account), second uses pad-ext
        (default config).
        """
        ledger = """
        option "plugin_processing_mode" "raw"
        plugin "beancount_lazy_plugins.pad_extended"
        plugin "beancount.ops.balance"

        2015-01-01 open Assets:Bank USD
        2015-01-01 open Equity:Opening-Balances USD
        2015-01-01 open Expenses:Unattributed USD
        2015-01-01 open Expenses:Unattributed:Bank USD

        2015-01-01 pad Assets:Bank Equity:Opening-Balances
        2015-01-02 balance Assets:Bank 100 USD
        2015-01-03 custom "pad-ext" Assets:Bank
        2015-01-04 balance Assets:Bank 150 USD
        """
        entries, errors, options_map = self.load_from_string(ledger)

        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")

        padding_txns = [
            e
            for e in entries
            if isinstance(e, data.Transaction) and e.flag == flags.FLAG_PADDING
        ]
        self.assertEqual(
            len(padding_txns),
            2,
            f"Expected 2 padding transactions, got {len(padding_txns)}",
        )

        # First padding: 100 USD from Pad directive, source Equity:Opening-Balances
        txn1 = padding_txns[0]
        self.assertEqual(txn1.date, datetime.date(2015, 1, 1))
        source_accounts = [
            p.account for p in txn1.postings if p.account != "Assets:Bank"
        ]
        self.assertEqual(
            source_accounts,
            ["Equity:Opening-Balances"],
            "First balance should use Pad's source_account",
        )
        amounts = {p.account: p.units for p in txn1.postings}
        self.assertEqual(amounts["Assets:Bank"], Amount(D("100"), "USD"))
        self.assertEqual(
            amounts["Equity:Opening-Balances"], Amount(D("-100"), "USD")
        )

        # Second padding: 50 USD from pad-ext, default Expenses:Unattributed:{name}
        txn2 = padding_txns[1]
        self.assertEqual(txn2.date, datetime.date(2015, 1, 3))
        source_accounts = [
            p.account for p in txn2.postings if p.account != "Assets:Bank"
        ]
        self.assertEqual(
            source_accounts,
            ["Expenses:Unattributed:Bank"],
            "Second balance should use pad-ext default config",
        )
        amounts = {p.account: p.units for p in txn2.postings}
        self.assertEqual(amounts["Assets:Bank"], Amount(D("50"), "USD"))
        self.assertEqual(
            amounts["Expenses:Unattributed:Bank"], Amount(D("-50"), "USD")
        )

    def test_requires_plugin_processing_mode_raw(self):
        """Test that pad_extended errors when plugin_processing_mode is not raw."""
        ledger = """
        option "plugin_processing_mode" "default"
        plugin "beancount_lazy_plugins.pad_extended"
        plugin "beancount.ops.balance"

        2015-01-01 open Assets:Bank USD
        2015-01-01 custom "pad-ext" Assets:Bank
        2015-01-02 balance Assets:Bank 0 USD
        """
        entries, errors, options_map = self.load_from_string(ledger)

        self.assertGreater(len(errors), 0)
        error_messages = [e.message for e in errors]
        self.assertTrue(
            any("plugin_processing_mode" in msg for msg in error_messages),
            f"Expected plugin_processing_mode error, got: {error_messages}",
        )

    def test_rejects_beancount_ops_pad(self):
        """Test that pad_extended errors when beancount.ops.pad is enabled."""
        ledger = """
        option "plugin_processing_mode" "raw"
        plugin "beancount_lazy_plugins.pad_extended"
        plugin "beancount.ops.pad"
        plugin "beancount.ops.balance"

        2015-01-01 open Assets:Bank USD
        2015-01-01 custom "pad-ext" Assets:Bank
        2015-01-02 balance Assets:Bank 0 USD
        """
        entries, errors, options_map = self.load_from_string(ledger)

        self.assertGreater(len(errors), 0)
        error_messages = [e.message for e in errors]
        self.assertTrue(
            any("beancount.ops.pad" in msg for msg in error_messages),
            f"Expected beancount.ops.pad error, got: {error_messages}",
        )
