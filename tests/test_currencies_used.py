"""Tests for the currencies_used plugin."""

import unittest
from decimal import Decimal
from beancount.core import data
from beancount.core.data import Amount, Open, Transaction, Posting
from beancount_lazy_plugins.currencies_used import currencies_used
import datetime

class TestCurrenciesUsed(unittest.TestCase):
    
    def setUp(self):
        """Set up test data."""
        self.maxDiff = None
        
    def test_basic_functionality(self):
        """Test basic currency tracking functionality."""
        entries = [
            # Open directives
            Open(
                meta={},
                date=datetime.date(2020, 1, 1),
                account="Assets:Cash",
                currencies=None,
                booking=None
            ),
            Open(
                meta={},
                date=datetime.date(2020, 1, 1),
                account="Assets:Investment",
                currencies=None,
                booking=None
            ),
            Open(
                meta={},
                date=datetime.date(2020, 1, 1),
                account="Income:Salary",
                currencies=None,
                booking=None
            ),
            # Transactions with different currencies
            Transaction(
                meta={},
                date=datetime.date(2020, 1, 2),
                flag="*",
                payee=None,
                narration="USD transaction",
                tags=None,
                links=None,
                postings=[
                    Posting(
                        account="Assets:Cash",
                        units=Amount(Decimal('1000'), "USD"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    ),
                    Posting(
                        account="Income:Salary",
                        units=Amount(Decimal('-1000'), "USD"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    )
                ]
            ),
            Transaction(
                meta={},
                date=datetime.date(2020, 1, 3),
                flag="*",
                payee=None,
                narration="EUR transaction",
                tags=None,
                links=None,
                postings=[
                    Posting(
                        account="Assets:Cash",
                        units=Amount(Decimal('500'), "EUR"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    ),
                    Posting(
                        account="Assets:Investment",
                        units=Amount(Decimal('-500'), "EUR"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    )
                ]
            ),
            Transaction(
                meta={},
                date=datetime.date(2020, 1, 4),
                flag="*",
                payee=None,
                narration="GBP transaction",
                tags=None,
                links=None,
                postings=[
                    Posting(
                        account="Assets:Cash",
                        units=Amount(Decimal('200'), "GBP"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    ),
                    Posting(
                        account="Assets:Investment",
                        units=Amount(Decimal('-200'), "GBP"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    )
                ]
            )
        ]
        
        new_entries, errors = currencies_used(entries, {})
        
        # Should have no errors
        self.assertEqual(len(errors), 0)
        
        # Check that Open directives have been updated with currencies_used metadata
        open_entries = [e for e in new_entries if isinstance(e, Open)]
        
        # Assets:Cash should have EUR, GBP, USD (sorted alphabetically)
        cash_open = next(e for e in open_entries if e.account == "Assets:Cash")
        self.assertEqual(cash_open.meta['currencies_used'], "EUR, GBP, USD")
        
        # Assets:Investment should have EUR, GBP
        investment_open = next(e for e in open_entries if e.account == "Assets:Investment")
        self.assertEqual(investment_open.meta['currencies_used'], "EUR, GBP")
        
        # Income:Salary should have USD
        salary_open = next(e for e in open_entries if e.account == "Income:Salary")
        self.assertEqual(salary_open.meta['currencies_used'], "USD")
        
    def test_no_transactions_for_account(self):
        """Test account with no transactions remains unchanged."""
        entries = [
            Open(
                meta={'existing_meta': 'value'},
                date=datetime.date(2020, 1, 1),
                account="Assets:Unused",
                currencies=None,
                booking=None
            )
        ]
        
        new_entries, errors = currencies_used(entries, {})
        
        # Should have no errors
        self.assertEqual(len(errors), 0)
        
        # Open directive should remain unchanged (no currencies_used added)
        open_entry = new_entries[0]
        self.assertIsInstance(open_entry, Open)
        self.assertEqual(open_entry.account, "Assets:Unused")
        self.assertEqual(open_entry.meta, {'existing_meta': 'value'})
        self.assertNotIn('currencies_used', open_entry.meta)
        
    def test_preserves_existing_metadata(self):
        """Test that existing metadata is preserved when adding currencies_used."""
        entries = [
            Open(
                meta={'existing_key': 'existing_value'},
                date=datetime.date(2020, 1, 1),
                account="Assets:Test",
                currencies=None,
                booking=None
            ),
            Transaction(
                meta={},
                date=datetime.date(2020, 1, 2),
                flag="*",
                payee=None,
                narration="Test transaction",
                tags=None,
                links=None,
                postings=[
                    Posting(
                        account="Assets:Test",
                        units=Amount(Decimal('100'), "USD"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    ),
                    Posting(
                        account="Income:Other",
                        units=Amount(Decimal('-100'), "USD"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    )
                ]
            )
        ]
        
        new_entries, errors = currencies_used(entries, {})
        
        # Should have no errors
        self.assertEqual(len(errors), 0)
        
        # Check that existing metadata is preserved
        open_entry = next(e for e in new_entries if isinstance(e, Open) and e.account == "Assets:Test")
        self.assertEqual(open_entry.meta['existing_key'], 'existing_value')
        self.assertEqual(open_entry.meta['currencies_used'], 'USD')

if __name__ == '__main__':
    unittest.main()
