"""
Tests for the balance_extended plugin.
"""

import datetime
import unittest
from decimal import Decimal

from beancount.core import data
from beancount.core import amount
from beancount.core.number import D
from beancount_lazy_plugins.balance_extended import balance_extended, BalanceExtendedError, BalanceType


class TestBalanceExtended(unittest.TestCase):
    """Test cases for balance_extended plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.options_map = {}

    def test_balance_full_single_currency(self):
        """Test balance full with a single currency."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Checking", D("100"), "USD"]
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 1)
        
        balance_entry = new_entries[0]
        self.assertIsInstance(balance_entry, data.Balance)
        self.assertEqual(balance_entry.account, "Assets:Checking")
        self.assertEqual(balance_entry.amount, amount.Amount(D("100"), "USD"))
        self.assertEqual(balance_entry.date, datetime.date(2015, 1, 1))

    def test_balance_full_multiple_currencies(self):
        """Test balance full with multiple currencies."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Checking", D("100"), "EUR", D("230"), "USD"]
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
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

    def test_balance_soft_single_currency(self):
        """Test balance soft with a single currency."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["soft", "Assets:Checking", "Equity:Opening-Balances", D("100"), "USD"]
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 2)
        
        # Check pad entry
        pad_entry = new_entries[0]
        self.assertIsInstance(pad_entry, data.Pad)
        self.assertEqual(pad_entry.account, "Assets:Checking")
        self.assertEqual(pad_entry.source_account, "Equity:Opening-Balances")
        self.assertEqual(pad_entry.date, datetime.date(2014, 12, 31))  # day-1
        
        # Check balance entry
        balance_entry = new_entries[1]
        self.assertIsInstance(balance_entry, data.Balance)
        self.assertEqual(balance_entry.account, "Assets:Checking")
        self.assertEqual(balance_entry.amount, amount.Amount(D("100"), "USD"))
        self.assertEqual(balance_entry.date, datetime.date(2015, 1, 1))

    def test_balance_soft_multiple_currencies(self):
        """Test balance soft with multiple currencies."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["soft", "Assets:Checking", "Equity:Opening-Balances", D("100"), "EUR", D("230"), "USD"]
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 3)
        
        # Check pad entry
        pad_entry = new_entries[0]
        self.assertIsInstance(pad_entry, data.Pad)
        self.assertEqual(pad_entry.account, "Assets:Checking")
        self.assertEqual(pad_entry.source_account, "Equity:Opening-Balances")
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

    def test_balance_full_string_amounts(self):
        """Test balance full with string amounts (should be converted to Decimal)."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Checking", "100.50", "USD"]
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 1)
        
        balance_entry = new_entries[0]
        self.assertIsInstance(balance_entry, data.Balance)
        self.assertEqual(balance_entry.amount, amount.Amount(D("100.50"), "USD"))

    def test_balance_full_insufficient_arguments(self):
        """Test balance full with insufficient arguments."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Checking"]  # Missing amount and currency
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("balance_type account amount1 currency1", errors[0].message)

    def test_balance_full_odd_number_of_values(self):
        """Test balance full with odd number of amount/currency values."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Checking", D("100"), "USD", D("200")]  # Missing currency for 200
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("pairs of amount and currency", errors[0].message)

    def test_balance_soft_insufficient_arguments(self):
        """Test balance soft with insufficient arguments."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["soft", "Assets:Checking", "Equity:Opening-Balances"]  # Missing amount and currency
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("balance_type account pad_account amount1 currency1", errors[0].message)

    def test_invalid_account_type(self):
        """Test with non-string account."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", 123, D("100"), "USD"]  # Account should be string
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("must be an account name (string)", errors[0].message)

    def test_invalid_amount_value(self):
        """Test with invalid amount value."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Checking", "invalid", "USD"]
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("Invalid amount value", errors[0].message)

    def test_non_string_currency(self):
        """Test with non-string currency."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Checking", D("100"), 123]  # Currency should be string
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("Currency must be a string", errors[0].message)

    def test_invalid_balance_type(self):
        """Test with invalid balance type."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["invalid", "Assets:Checking", D("100"), "USD"]  # Invalid balance type
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("Invalid balance type: invalid", errors[0].message)
        self.assertIn("Must be 'full' or 'soft'", errors[0].message)

    def test_non_string_balance_type(self):
        """Test with non-string balance type."""
        meta = data.new_metadata("test.beancount", 1)
        custom_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=[123, "Assets:Checking", D("100"), "USD"]  # Balance type should be string
        )
        
        entries = [custom_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(new_entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BalanceExtendedError)
        self.assertIn("First argument to balance-ext must be balance type (string)", errors[0].message)

    def test_other_custom_directives_preserved(self):
        """Test that other custom directives are preserved."""
        meta = data.new_metadata("test.beancount", 1)
        other_custom = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="other-custom",
            values=["some", "values"]
        )
        
        entries = [other_custom]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 1)
        self.assertEqual(new_entries[0], other_custom)

    def test_non_custom_directives_preserved(self):
        """Test that non-custom directives are preserved."""
        meta = data.new_metadata("test.beancount", 1)
        open_entry = data.Open(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            account="Assets:Checking",
            currencies=["USD"],
            booking=None
        )
        
        entries = [open_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 1)
        self.assertEqual(new_entries[0], open_entry)

    def test_mixed_entries(self):
        """Test with a mix of custom and non-custom entries."""
        meta = data.new_metadata("test.beancount", 1)
        
        open_entry = data.Open(
            meta=meta,
            date=datetime.date(2014, 12, 31),
            account="Assets:Checking",
            currencies=["USD", "EUR"],
            booking=None
        )
        
        balance_full_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Checking", D("100"), "EUR", D("230"), "USD"]
        )
        
        balance_soft_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 2, 1),
            type="balance-ext",
            values=["soft", "Assets:Checking", "Equity:Opening-Balances", D("150"), "EUR"]
        )
        
        entries = [open_entry, balance_full_entry, balance_soft_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 6)  # 1 open + 2 balance full + 1 pad + 1 balance soft
        
        # Check that open entry is preserved
        self.assertEqual(new_entries[0], open_entry)
        
        # Check balance full entries
        self.assertIsInstance(new_entries[1], data.Balance)
        self.assertIsInstance(new_entries[2], data.Balance)
        
        # Check balance soft entries (pad + balance)
        self.assertIsInstance(new_entries[3], data.Pad)
        self.assertIsInstance(new_entries[4], data.Balance)

    def test_balance_full_with_zero_currencies(self):
        """Test balance full creates zero balance assertions for missing currencies."""
        meta = data.new_metadata("test.beancount", 1)
        
        # Open account with multiple currencies
        open_entry = data.Open(
            meta=meta,
            date=datetime.date(2014, 12, 31),
            account="Assets:Checking",
            currencies=["USD", "EUR", "GBP"],
            booking=None
        )
        
        # Balance directive only specifies USD, should create EUR and GBP as 0
        balance_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Checking", D("100"), "USD"]
        )
        
        entries = [open_entry, balance_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 4)  # 1 open + 3 balance assertions
        
        # Check that open entry is preserved
        self.assertEqual(new_entries[0], open_entry)
        
        # Check balance assertions - should be sorted by currency
        balance_assertions = [e for e in new_entries[1:] if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 3)
        
        # Should be sorted: EUR (0), GBP (0), USD (100)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("0"), "EUR"))
        self.assertEqual(balance_assertions[1].amount, amount.Amount(D("0"), "GBP"))
        self.assertEqual(balance_assertions[2].amount, amount.Amount(D("100"), "USD"))

    def test_balance_soft_with_zero_currencies(self):
        """Test balance soft creates zero balance assertions for missing currencies."""
        meta = data.new_metadata("test.beancount", 1)
        
        # Open account with multiple currencies
        open_entry = data.Open(
            meta=meta,
            date=datetime.date(2014, 12, 31),
            account="Assets:Checking",
            currencies=["USD", "EUR", "CAD"],
            booking=None
        )
        
        # Balance directive only specifies EUR, should create USD and CAD as 0
        balance_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["soft", "Assets:Checking", "Equity:Opening-Balances", D("50"), "EUR"]
        )
        
        entries = [open_entry, balance_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 5)  # 1 open + 1 pad + 3 balance assertions
        
        # Check that open entry is preserved
        self.assertEqual(new_entries[0], open_entry)
        
        # Check pad entry
        self.assertIsInstance(new_entries[1], data.Pad)
        self.assertEqual(new_entries[1].account, "Assets:Checking")
        self.assertEqual(new_entries[1].source_account, "Equity:Opening-Balances")
        
        # Check balance assertions - should be sorted by currency
        balance_assertions = [e for e in new_entries[2:] if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 3)
        
        # Should be sorted: CAD (0), EUR (50), USD (0)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("0"), "CAD"))
        self.assertEqual(balance_assertions[1].amount, amount.Amount(D("50"), "EUR"))
        self.assertEqual(balance_assertions[2].amount, amount.Amount(D("0"), "USD"))

    def test_balance_full_no_open_directive(self):
        """Test balance full when account has no Open directive."""
        meta = data.new_metadata("test.beancount", 1)
        
        # No open directive for the account
        balance_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Unknown", D("100"), "USD", D("50"), "EUR"]
        )
        
        entries = [balance_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
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
        meta = data.new_metadata("test.beancount", 1)
        
        # Open account with no currencies specified
        open_entry = data.Open(
            meta=meta,
            date=datetime.date(2014, 12, 31),
            account="Assets:Checking",
            currencies=None,  # No currencies specified
            booking=None
        )
        
        balance_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="balance-ext",
            values=["full", "Assets:Checking", D("100"), "USD"]
        )
        
        entries = [open_entry, balance_entry]
        new_entries, errors = balance_extended(entries, self.options_map)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(new_entries), 2)  # 1 open + 1 balance assertion
        
        # Check that open entry is preserved
        self.assertEqual(new_entries[0], open_entry)
        
        # Check balance assertion - should only create what's specified
        balance_assertions = [e for e in new_entries[1:] if isinstance(e, data.Balance)]
        self.assertEqual(len(balance_assertions), 1)
        self.assertEqual(balance_assertions[0].amount, amount.Amount(D("100"), "USD"))

    def test_build_account_currencies_mapping(self):
        """Test the build_account_currencies_mapping function directly."""
        from beancount_lazy_plugins.balance_extended import build_account_currencies_mapping
        
        meta = data.new_metadata("test.beancount", 1)
        
        # Create some Open entries
        open1 = data.Open(
            meta=meta,
            date=datetime.date(2014, 12, 31),
            account="Assets:Checking",
            currencies=["USD", "EUR"],
            booking=None
        )
        
        open2 = data.Open(
            meta=meta,
            date=datetime.date(2014, 12, 31),
            account="Assets:Savings",
            currencies=["USD", "CAD", "GBP"],
            booking=None
        )
        
        open3 = data.Open(
            meta=meta,
            date=datetime.date(2014, 12, 31),
            account="Assets:Investment",
            currencies=None,  # No currencies
            booking=None
        )
        
        # Add some non-Open entries that should be ignored
        other_entry = data.Custom(
            meta=meta,
            date=datetime.date(2015, 1, 1),
            type="other",
            values=["test"]
        )
        
        entries = [open1, open2, open3, other_entry]
        mapping = build_account_currencies_mapping(entries)
        
        expected = {
            "Assets:Checking": {"USD", "EUR"},
            "Assets:Savings": {"USD", "CAD", "GBP"},
            "Assets:Investment": set()  # Empty set for None currencies
        }
        
        self.assertEqual(mapping, expected)


if __name__ == '__main__':
    unittest.main()
