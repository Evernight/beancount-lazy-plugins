"""
Tests for the balance_extended plugin.
"""

import datetime
import unittest
from decimal import Decimal
from textwrap import dedent

from beancount.core import data
from beancount.core import amount
from beancount.core.number import D
from beancount.loader import load_string
from beancount_lazy_plugins.balance_extended import balance_extended, BalanceExtendedError, BalanceType


class TestBalanceExtended(unittest.TestCase):
    """Test cases for balance_extended plugin."""

    def load_from_string(self, text):
        entries, errors, options_map = load_string(dedent(text))
        return entries, options_map

    def test_balance_full_single_currency(self):
        """Test full type balance with a single currency."""
        ledger = """
        2015-01-01 custom "balance-ext" "full" Assets:Checking 100 USD
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 1)

        balance_entry = new_entries[0]
        self.assertIsInstance(balance_entry, data.Balance)
        self.assertEqual(balance_entry.account, "Assets:Checking")
        self.assertEqual(balance_entry.amount, amount.Amount(D("100"), "USD"))
        self.assertEqual(balance_entry.date, datetime.date(2015, 1, 1))

    def test_balance_full_multiple_currencies(self):
        """Test full type balance with multiple currencies."""
        ledger = """
        2015-01-01 custom "balance-ext" "full" Assets:Checking 100 EUR 230 USD
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 2)

        # Check first balance entry (EUR)
        balance_entry_1 = new_entries[0]
        self.assertIsInstance(balance_entry_1, data.Balance)
        self.assertEqual(balance_entry_1.account, "Assets:Checking")
        self.assertEqual(balance_entry_1.amount, amount.Amount(D("100"), "EUR"))
        self.assertEqual(balance_entry_1.date, datetime.date(2015, 1, 1))

        # Check second balance entry (USD)
        balance_entry_2 = new_entries[1]
        self.assertIsInstance(balance_entry_2, data.Balance)
        self.assertEqual(balance_entry_2.account, "Assets:Checking")
        self.assertEqual(balance_entry_2.amount, amount.Amount(D("230"), "USD"))
        self.assertEqual(balance_entry_2.date, datetime.date(2015, 1, 1))

    def test_balance_padded_single_currency(self):
        """Test padded type balance with a single currency."""
        ledger = """
        2015-01-01 custom "balance-ext" "padded" Assets:Checking 100 USD
            pad_account: "Equity:Opening-Balances"
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 2)

        # Check pad entry
        pad_entry = new_entries[0]
        self.assertIsInstance(pad_entry, data.Custom)
        self.assertEqual(pad_entry.type, "pad-ext")
        self.assertEqual(pad_entry.values[0].value, "Assets:Checking")
        self.assertEqual(pad_entry.meta.get("pad_account"), "Equity:Opening-Balances")
        self.assertEqual(pad_entry.date, datetime.date(2014, 12, 31))  # day-1

        # Check balance entry
        balance_entry = new_entries[1]
        self.assertIsInstance(balance_entry, data.Balance)
        self.assertEqual(balance_entry.account, "Assets:Checking")
        self.assertEqual(balance_entry.amount, amount.Amount(D("100"), "USD"))
        self.assertEqual(balance_entry.date, datetime.date(2015, 1, 1))

    def test_balance_type_config_applies_by_regex(self):
        """Use balance-ext-config to set default balance type by account regex."""
        ledger = """
        2014-12-31 open Assets:Checking USD,EUR
        2015-01-01 custom "balance-ext-config"
          account_regex: "Assets:.*"
          balance_type: "full-padded"
        2015-01-01 custom "balance-ext" Assets:Checking 100 USD
            pad_account: "Equity:Opening-Balances"
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 5)  # open + config + pad + 2 balances

        self.assertEqual(new_entries[0], entries[0])  # open preserved
        self.assertEqual(new_entries[1], entries[1])  # config preserved

        pad_entry = new_entries[2]
        self.assertIsInstance(pad_entry, data.Custom)
        self.assertEqual(pad_entry.type, "pad-ext")
        self.assertEqual(pad_entry.values[0].value, "Assets:Checking")
        self.assertEqual(pad_entry.meta.get("pad_account"), "Equity:Opening-Balances")
        self.assertEqual(pad_entry.date, datetime.date(2014, 12, 31))  # day-1

        balance_assertions = [e for e in new_entries[3:] if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 2)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("0"), "EUR"))
        self.assertEqual(balance_assertions[1].amount, amount.Amount(D("100"), "USD"))

    def test_balance_padded_does_not_create_duplicate_pad_for_same_key(self):
        """If multiple padded type balance-ext directives would create the same Pad, emit it once."""
        ledger = """
        2015-01-01 custom "balance-ext" "padded" Assets:Checking 100 USD
            pad_account: "Equity:Opening-Balances"
        2015-01-01 custom "balance-ext" "padded" Assets:Checking 150 EUR
            pad_account: "Equity:Opening-Balances"
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        pad_ext_entries = [
            e for e in new_entries
            if isinstance(e, data.Custom) and e.type == "pad-ext"
        ]
        balances = [e for e in new_entries if isinstance(e, data.Balance)]

        self.assertEqual(len(pad_ext_entries), 1)
        pad_entry = pad_ext_entries[0]
        self.assertEqual(pad_entry.values[0].value, "Assets:Checking")
        self.assertEqual(pad_entry.meta.get("pad_account"), "Equity:Opening-Balances")
        self.assertEqual(pad_entry.date, datetime.date(2014, 12, 31))  # day-1

        # Both directives should still produce their balance assertion.
        self.assertEqual(len(balances), 2)
        self.assertEqual(balances[0].amount.currency, "USD")
        self.assertEqual(balances[1].amount.currency, "EUR")

    def test_balance_padded_does_not_create_pad_if_it_already_exists(self):
        """If a matching Pad already exists in the input entries, do not create another one."""
        ledger = """
        2014-01-01 open Assets:Checking
        2014-01-01 open Equity:Opening-Balances
        2014-12-31 pad Assets:Checking Equity:Opening-Balances
        2015-01-01 custom "balance-ext" "padded" Assets:Checking 100 USD
            pad_account: "Equity:Opening-Balances"
        2015-01-05 balance Assets:Checking 100 USD
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        pads = [e for e in new_entries if isinstance(e, data.Pad)]
        self.assertEqual(len(pads), 1)
        self.assertEqual(pads[0].account, "Assets:Checking")
        self.assertEqual(pads[0].source_account, "Equity:Opening-Balances")

    def test_balance_padded_multiple_currencies(self):
        """Test padded type balance with multiple currencies."""
        ledger = """
        2015-01-01 custom "balance-ext" "padded" Assets:Checking 100 EUR 230 USD
            pad_account: "Equity:Opening-Balances"
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 3)

        # Check pad entry
        pad_entry = new_entries[0]
        self.assertIsInstance(pad_entry, data.Custom)
        self.assertEqual(pad_entry.type, "pad-ext")
        self.assertEqual(pad_entry.values[0].value, "Assets:Checking")
        self.assertEqual(pad_entry.meta.get("pad_account"), "Equity:Opening-Balances")
        self.assertEqual(pad_entry.date, datetime.date(2014, 12, 31))  # day-1

        # Check first balance entry (EUR)
        balance_entry_1 = new_entries[1]
        self.assertIsInstance(balance_entry_1, data.Balance)
        self.assertEqual(balance_entry_1.account, "Assets:Checking")
        self.assertEqual(balance_entry_1.amount, amount.Amount(D("100"), "EUR"))
        self.assertEqual(balance_entry_1.date, datetime.date(2015, 1, 1))

        # Check second balance entry (USD)
        balance_entry_2 = new_entries[2]
        self.assertIsInstance(balance_entry_2, data.Balance)
        self.assertEqual(balance_entry_2.account, "Assets:Checking")
        self.assertEqual(balance_entry_2.amount, amount.Amount(D("230"), "USD"))
        self.assertEqual(balance_entry_2.date, datetime.date(2015, 1, 1))

    def test_balance_full_insufficient_arguments(self):
        """Test full type balance with insufficient arguments."""
        ledger = """
        2015-01-01 custom "balance-ext" "full" Assets:Checking
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("[balance_type] account amount1", errors[0].message)

    def test_balance_full_invalid_amount_object(self):
        """Test full type balance with invalid amount object."""
        ledger = """
        2015-01-01 custom "balance-ext" "full" Assets:Checking 100 USD 200
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(new_entries), 1)  # First amount should work
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("Expected Amount object", errors[0].message)

    def test_invalid_account_type(self):
        """Test with non-string account."""
        ledger = """
        2015-01-01 custom "balance-ext" "full" 123 100 USD
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("must be an account name (string)", errors[0].message)

    def test_invalid_amount_value(self):
        """Test with invalid amount value (not an Amount object)."""
        ledger = """
        2015-01-01 custom "balance-ext" "full" Assets:Checking "invalid"
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("Expected Amount object", errors[0].message)

    def test_mixed_entries(self):
        """Test with a mix of different types of entries."""
        ledger = """
        2014-12-31 open Assets:Checking USD,EUR
        2015-01-01 custom "balance-ext" "full" Assets:Checking 100 EUR 230 USD
        2015-02-01 custom "balance-ext" "padded" Assets:Checking 150 EUR
            pad_account: "Equity:Opening-Balances"
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 5)  # 1 open + 2 balance full + 1 pad + 1 balance padded

        # Check that open entry is preserved
        self.assertEqual(new_entries[0], entries[0])

        # Check balance full entries
        self.assertIsInstance(new_entries[1], data.Balance)
        self.assertIsInstance(new_entries[2], data.Balance)

        # Check balance padded entries (pad + balance)
        self.assertIsInstance(new_entries[3], data.Custom)
        self.assertEqual(new_entries[3].type, "pad-ext")
        self.assertIsInstance(new_entries[4], data.Balance)

    def test_balance_full_with_zero_currencies(self):
        """Test balance full creates zero balance assertions for missing currencies."""
        ledger = """
        2014-12-31 open Assets:Checking USD,EUR,GBP
        2015-01-01 custom "balance-ext" "full" Assets:Checking 100 USD
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 4)  # 1 open + 3 balance assertions

        # Check that open entry is preserved
        self.assertEqual(new_entries[0], entries[0])

        # Check balance assertions - should be sorted by currency
        balance_assertions = [e for e in new_entries[1:] if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 3)

        # Should be sorted: EUR (0), GBP (0), USD (100)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("0"), "EUR"))
        self.assertEqual(balance_assertions[1].amount, amount.Amount(D("0"), "GBP"))
        self.assertEqual(balance_assertions[2].amount, amount.Amount(D("100"), "USD"))

    def test_balance_padded_with_zero_currencies(self):
        """Test balance padded does not create zero balance assertions for missing currencies."""
        ledger = """
        2014-12-31 open Assets:Checking USD,EUR,CAD
        2015-01-01 custom "balance-ext" "padded" Assets:Checking 50 EUR
            pad_account: "Equity:Opening-Balances"
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 3)  # 1 open + 1 pad + 1 balance assertion

        # Check that open entry is preserved
        self.assertEqual(new_entries[0], entries[0])

        # Check pad entry
        pad_entry = new_entries[1]
        self.assertIsInstance(pad_entry, data.Custom)
        self.assertEqual(pad_entry.type, "pad-ext")
        self.assertEqual(pad_entry.values[0].value, "Assets:Checking")
        self.assertEqual(pad_entry.meta.get("pad_account"), "Equity:Opening-Balances")

        # Check balance assertions - should be sorted by currency
        balance_assertions = [e for e in new_entries[2:] if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 1)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("50"), "EUR"))

    def test_balance_full_no_open_directive(self):
        """Test balance full when account has no Open directive."""
        ledger = """
        2015-01-01 custom "balance-ext" "full" Assets:Unknown 100 USD 50 EUR
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 2)  # 2 balance assertions only

        # Check balance assertions - should only create what's specified
        balance_assertions = [e for e in new_entries if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 2)

        # Should be sorted: EUR (50), USD (100)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("50"), "EUR"))
        self.assertEqual(balance_assertions[1].amount, amount.Amount(D("100"), "USD"))

    def test_balance_full_empty_currencies_in_open(self):
        """Test balance full when Open directive has no currencies specified."""
        ledger = """
        2014-12-31 open Assets:Checking
        2015-01-01 custom "balance-ext" "full" Assets:Checking 100 USD
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 2)  # 1 open + 1 balance assertion

        # Check that open entry is preserved
        self.assertEqual(new_entries[0], entries[0])

        # Check balance assertion - should only create what's specified
        balance_assertions = [e for e in new_entries[1:] if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 1)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("100"), "USD"))

    def test_build_account_currencies_mapping(self):
        """Test the build_account_currencies_mapping function directly."""
        from beancount_lazy_plugins.balance_extended import build_account_currencies_mapping

        ledger = """
        2014-12-31 open Assets:Checking USD,EUR
        2014-12-31 open Assets:Savings USD,CAD,GBP
        2014-12-31 open Assets:Investment
        2015-01-01 custom "other" "test"
        """
        entries, _ = self.load_from_string(ledger)
        mapping = build_account_currencies_mapping(entries)

        expected = {
            "Assets:Checking": {"USD", "EUR"},
            "Assets:Savings": {"USD", "CAD", "GBP"},
            "Assets:Investment": set()
        }

        self.assertEqual(mapping, expected)

    def test_balance_full_padded_single_currency(self):
        """Test balance full-padded with a single currency."""
        ledger = """
        2014-12-31 open Assets:Checking USD,EUR,GBP
        2015-01-01 custom "balance-ext" "full-padded" Assets:Checking 100 USD
            pad_account: "Equity:Opening-Balances"
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 5)  # 1 open + 1 pad + 3 balance assertions

        # Check that open entry is preserved
        self.assertEqual(new_entries[0], entries[0])

        # Check pad entry
        pad_entry = new_entries[1]
        self.assertIsInstance(pad_entry, data.Custom)
        self.assertEqual(pad_entry.type, "pad-ext")
        self.assertEqual(pad_entry.values[0].value, "Assets:Checking")
        self.assertEqual(pad_entry.meta.get("pad_account"), "Equity:Opening-Balances")
        self.assertEqual(pad_entry.date, datetime.date(2014, 12, 31))  # day-1

        # Check balance assertions - should be sorted by currency
        balance_assertions = [e for e in new_entries[2:] if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 3)

        # Should be sorted: EUR (0), GBP (0), USD (100)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("0"), "EUR"))
        self.assertEqual(balance_assertions[1].amount, amount.Amount(D("0"), "GBP"))
        self.assertEqual(balance_assertions[2].amount, amount.Amount(D("100"), "USD"))

    def test_balance_full_padded_multiple_currencies(self):
        """Test balance full-padded with multiple currencies."""
        ledger = """
        2014-12-31 open Assets:Checking USD,EUR,GBP,CAD
        2015-01-01 custom "balance-ext" "full-padded" Assets:Checking 100 USD 50 EUR
            pad_account: "Equity:Opening-Balances"
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 6)  # 1 open + 1 pad + 4 balance assertions

        # Check that open entry is preserved
        self.assertEqual(new_entries[0], entries[0])

        # Check pad entry
        pad_entry = new_entries[1]
        self.assertIsInstance(pad_entry, data.Custom)
        self.assertEqual(pad_entry.type, "pad-ext")
        self.assertEqual(pad_entry.values[0].value, "Assets:Checking")
        self.assertEqual(pad_entry.meta.get("pad_account"), "Equity:Opening-Balances")
        self.assertEqual(pad_entry.date, datetime.date(2014, 12, 31))  # day-1

        # Check balance assertions - should be sorted by currency
        balance_assertions = [e for e in new_entries[2:] if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 4)

        # Should be sorted: CAD (0), EUR (50), GBP (0), USD (100)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("0"), "CAD"))
        self.assertEqual(balance_assertions[1].amount, amount.Amount(D("50"), "EUR"))
        self.assertEqual(balance_assertions[2].amount, amount.Amount(D("0"), "GBP"))
        self.assertEqual(balance_assertions[3].amount, amount.Amount(D("100"), "USD"))

    def test_balance_full_padded_no_open_directive(self):
        """Test balance full-padded when account has no Open directive."""
        ledger = """
        2015-01-01 custom "balance-ext" "full-padded" Assets:Unknown 100 USD 50 EUR
            pad_account: "Equity:Opening-Balances"
        """
        entries, options_map = self.load_from_string(ledger)
        new_entries, errors = balance_extended(entries, options_map)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 3)  # 1 pad + 2 balance assertions only

        # Check pad entry
        pad_entry = new_entries[0]
        self.assertIsInstance(pad_entry, data.Custom)
        self.assertEqual(pad_entry.type, "pad-ext")
        self.assertEqual(pad_entry.values[0].value, "Assets:Unknown")
        self.assertEqual(pad_entry.meta.get("pad_account"), "Equity:Opening-Balances")

        # Check balance assertions - should only create what's specified
        balance_assertions = [e for e in new_entries[1:] if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 2)

        # Should be sorted: EUR (50), USD (100)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("50"), "EUR"))
        self.assertEqual(balance_assertions[1].amount, amount.Amount(D("100"), "USD"))


if __name__ == '__main__':
    unittest.main()
