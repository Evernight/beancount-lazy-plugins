"""Tests for the currencies_used plugin."""

import unittest
from decimal import Decimal
from beancount.core import data
from beancount.core.data import Amount, Open, Transaction, Posting, Pad, Balance
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

    def test_extend_from_pad_directives_propagates_currencies_from_padded_account(self):
        """Currencies from padded account should extend to source_account; Balance currencies are included."""
        entries = [
            # Open directives for padded and source accounts
            Open(
                meta={},
                date=datetime.date(2020, 1, 1),
                account="Assets:Cash",  # Padded account
                currencies=None,
                booking=None
            ),
            Open(
                meta={},
                date=datetime.date(2020, 1, 1),
                account="Equity:Opening-Balances",  # Source account
                currencies=None,
                booking=None
            ),
            # A transaction that establishes USD usage on the padded account
            Transaction(
                meta={},
                date=datetime.date(2020, 1, 2),
                flag="*",
                payee=None,
                narration="Seed USD on padded account",
                tags=None,
                links=None,
                postings=[
                    Posting(
                        account="Assets:Cash",
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
                    ),
                ],
            ),
            # Pad directive linking padded account to source account
            Pad(
                meta={},
                date=datetime.date(2020, 1, 2),
                account="Assets:Cash",
                source_account="Equity:Opening-Balances",
            ),
            # Balance directive on source account in EUR should contribute EUR
            Balance(
                meta={},
                date=datetime.date(2020, 1, 3),
                account="Equity:Opening-Balances",
                amount=Amount(Decimal('10'), "EUR"),
                tolerance=None,
                diff_amount=None,
            ),
        ]

        config_str = "{'extend_from_pad_directives': True}"
        new_entries, errors = currencies_used(entries, {}, config_str)

        # No errors expected
        self.assertEqual(len(errors), 0)

        # The padded account should include USD as usual
        cash_open = next(e for e in new_entries if isinstance(e, Open) and e.account == "Assets:Cash")
        self.assertEqual(cash_open.meta.get('currencies_used'), 'USD')

        # The source account should include USD via Pad and EUR via Balance (sorted)
        source_open = next(e for e in new_entries if isinstance(e, Open) and e.account == "Equity:Opening-Balances")
        self.assertEqual(source_open.meta.get('currencies_used'), 'EUR, USD')
    
    def test_extend_open_directives_add_currencies(self):
        """Test extend_open_directives adds currencies to Open directives with None currencies."""
        entries = [
            # Open directive with no currencies defined
            Open(
                meta={},
                date=datetime.date(2020, 1, 1),
                account="Assets:Cash",
                currencies=None,  # No currencies defined
                booking=None
            ),
            # Transaction using multiple currencies
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
                        account="Expenses:Other",
                        units=Amount(Decimal('-500'), "EUR"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    )
                ]
            )
        ]
        
        # Test with extend_open_directives enabled
        config_str = "{'extend_open_directives': True}"
        new_entries, errors = currencies_used(entries, {}, config_str)
        
        # Should have no errors
        self.assertEqual(len(errors), 0)
        
        # Check that Open directive now has currencies defined
        cash_open = next(e for e in new_entries if isinstance(e, Open) and e.account == "Assets:Cash")
        self.assertEqual(cash_open.currencies, ["EUR", "USD"])  # Should be sorted
        self.assertEqual(cash_open.meta['currencies_used'], "EUR, USD")
    
    def test_extend_open_directives_validate_currencies_match(self):
        """Test extend_open_directives validates matching currencies without error."""
        entries = [
            # Open directive with currencies that match usage
            Open(
                meta={},
                date=datetime.date(2020, 1, 1),
                account="Assets:Cash",
                currencies=["USD", "EUR"],  # Matches what will be used
                booking=None
            ),
            # Transactions using the same currencies
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
                        account="Expenses:Other",
                        units=Amount(Decimal('-500'), "EUR"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    )
                ]
            )
        ]
        
        # Test with extend_open_directives enabled
        config_str = "{'extend_open_directives': True}"
        new_entries, errors = currencies_used(entries, {}, config_str)
        
        # Should have no errors since currencies match
        self.assertEqual(len(errors), 0)
        
        # Open directive currencies should remain unchanged
        cash_open = next(e for e in new_entries if isinstance(e, Open) and e.account == "Assets:Cash")
        self.assertEqual(cash_open.currencies, ["USD", "EUR"])
        self.assertEqual(cash_open.meta['currencies_used'], "EUR, USD")
    
    def test_extend_open_directives_validate_currencies_mismatch(self):
        """Test extend_open_directives reports error when currencies don't match."""
        entries = [
            # Open directive with currencies that don't match usage
            Open(
                meta={},
                date=datetime.date(2020, 1, 1),
                account="Assets:Cash",
                currencies=["USD"],  # Only USD defined, but EUR will be used too
                booking=None
            ),
            # Transactions using more currencies than defined
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
                        account="Expenses:Other",
                        units=Amount(Decimal('-500'), "EUR"),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None
                    )
                ]
            )
        ]
        
        # Test with extend_open_directives enabled
        config_str = "{'extend_open_directives': True}"
        new_entries, errors = currencies_used(entries, {}, config_str)
        
        # Should have one error for currency mismatch
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertIn("Assets:Cash", error.message)
        self.assertIn("defined currencies ['USD']", error.message)
        self.assertIn("used currencies ['EUR', 'USD']", error.message)
        
        # Open directive currencies should remain unchanged
        cash_open = next(e for e in new_entries if isinstance(e, Open) and e.account == "Assets:Cash")
        self.assertEqual(cash_open.currencies, ["USD"])  # Original currencies preserved
        self.assertEqual(cash_open.meta['currencies_used'], "EUR, USD")
    
    def test_config_disabled_no_extension(self):
        """Test that without extend_open_directives config, behavior is unchanged."""
        entries = [
            Open(
                meta={},
                date=datetime.date(2020, 1, 1),
                account="Assets:Cash",
                currencies=None,
                booking=None
            ),
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
            )
        ]
        
        # Test without config (default behavior)
        new_entries, errors = currencies_used(entries, {})
        
        # Should have no errors
        self.assertEqual(len(errors), 0)
        
        # Open directive currencies should remain None (unchanged)
        cash_open = next(e for e in new_entries if isinstance(e, Open) and e.account == "Assets:Cash")
        self.assertIsNone(cash_open.currencies)
        self.assertEqual(cash_open.meta['currencies_used'], "USD")
    
    def test_invalid_config_string(self):
        """Test that invalid config string produces error."""
        entries = [
            Open(
                meta={},
                date=datetime.date(2020, 1, 1),
                account="Assets:Cash",
                currencies=None,
                booking=None
            )
        ]
        
        # Test with invalid config string
        config_str = "invalid python syntax {"
        new_entries, errors = currencies_used(entries, {}, config_str)
        
        # Should have one error for invalid config
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertIn("Invalid configuration string", error.message)
        
        # Should return original entries unchanged
        self.assertEqual(len(new_entries), 1)
        self.assertEqual(new_entries[0], entries[0])

if __name__ == '__main__':
    unittest.main()
