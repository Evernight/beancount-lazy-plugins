"""
Tests for the currency_convert plugin functionality.
"""
import pytest
import io
from pathlib import Path
from decimal import Decimal
from datetime import date

from beancount import loader
from beancount.core.data import Amount, Posting, Price, Transaction
from beancount.parser import printer
from beancount_lazy_plugins.currency_convert import currency_convert


def test_currency_convert_basic():
    """Test basic currency conversion functionality."""
    # Create test data
    entries = [
        # Price data
        Price(
            meta={},
            date=date(2024, 1, 1),
            currency='EUR',
            amount=Amount(Decimal('1.2'), 'USD')
        ),
        Price(
            meta={},
            date=date(2024, 1, 2),
            currency='GBP',
            amount=Amount(Decimal('1.3'), 'USD')
        ),
        # Transaction with convert_to metadata
        Transaction(
            meta={},
            date=date(2024, 1, 1),
            flag='*',
            payee=None,
            narration='Test conversion',
            tags=set(),
            links=set(),
            postings=[
                Posting(
                    account='Assets:Cash',
                    units=Amount(Decimal('100'), 'EUR'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={'convert_to': 'USD'}
                ),
                Posting(
                    account='Expenses:Test',
                    units=Amount(Decimal('-100'), 'EUR'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta=None
                )
            ]
        )
    ]
    
    options_map = {}
    
    # Run the plugin
    new_entries, errors = currency_convert(entries, options_map)
    
    # Check for no errors
    assert len(errors) == 0, f"Unexpected errors: {errors}"
    
    # Find the modified transaction
    transactions = [e for e in new_entries if isinstance(e, Transaction)]
    assert len(transactions) == 1
    
    transaction = transactions[0]
    
    # Check that the first posting was converted
    first_posting = transaction.postings[0]
    assert first_posting.units.currency == 'USD'
    assert first_posting.units.number == Decimal('120')  # 100 * 1.2
    assert 'convert_to' not in (first_posting.meta or {})
    assert first_posting.meta['converted_from'] == '100 EUR'
    
    # Check that the second posting was unchanged
    second_posting = transaction.postings[1]
    assert second_posting.units.currency == 'EUR'
    assert second_posting.units.number == Decimal('-100')


def test_currency_convert_no_conversion_needed():
    """Test that postings without convert_to metadata are unchanged."""
    entries = [
        Transaction(
            meta={},
            date=date(2024, 1, 1),
            flag='*',
            payee=None,
            narration='Test no conversion',
            tags=set(),
            links=set(),
            postings=[
                Posting(
                    account='Assets:Cash',
                    units=Amount(Decimal('100'), 'USD'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta=None
                )
            ]
        )
    ]
    
    options_map = {}
    
    # Run the plugin
    new_entries, errors = currency_convert(entries, options_map)
    
    # Check for no errors
    assert len(errors) == 0
    
    # Check that the transaction is unchanged
    assert new_entries == entries


def test_currency_convert_same_currency():
    """Test that convert_to metadata is removed when source and target are the same."""
    entries = [
        Transaction(
            meta={},
            date=date(2024, 1, 1),
            flag='*',
            payee=None,
            narration='Test same currency',
            tags=set(),
            links=set(),
            postings=[
                Posting(
                    account='Assets:Cash',
                    units=Amount(Decimal('100'), 'USD'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={'convert_to': 'USD'}
                )
            ]
        )
    ]
    
    options_map = {}
    
    # Run the plugin
    new_entries, errors = currency_convert(entries, options_map)
    
    # Check for no errors
    assert len(errors) == 0
    
    # Find the modified transaction
    transactions = [e for e in new_entries if isinstance(e, Transaction)]
    assert len(transactions) == 1
    
    transaction = transactions[0]
    posting = transaction.postings[0]
    
    # Check that the posting amount is unchanged but metadata is removed
    assert posting.units.currency == 'USD'
    assert posting.units.number == Decimal('100')
    assert 'convert_to' not in (posting.meta or {})


def test_currency_convert_inverse_rate():
    """Test currency conversion using inverse exchange rates."""
    entries = [
        # Price data (USD to EUR)
        Price(
            meta={},
            date=date(2024, 1, 1),
            currency='USD',
            amount=Amount(Decimal('0.8'), 'EUR')
        ),
        # Transaction converting EUR to USD (needs inverse rate)
        Transaction(
            meta={},
            date=date(2024, 1, 1),
            flag='*',
            payee=None,
            narration='Test inverse conversion',
            tags=set(),
            links=set(),
            postings=[
                Posting(
                    account='Assets:Cash',
                    units=Amount(Decimal('80'), 'EUR'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={'convert_to': 'USD'}
                )
            ]
        )
    ]
    
    options_map = {}
    
    # Run the plugin
    new_entries, errors = currency_convert(entries, options_map)
    
    # Check for no errors
    assert len(errors) == 0
    
    # Find the modified transaction
    transactions = [e for e in new_entries if isinstance(e, Transaction)]
    assert len(transactions) == 1
    
    transaction = transactions[0]
    posting = transaction.postings[0]
    
    # Check that the posting was converted using inverse rate
    # 80 EUR * (1 / 0.8) = 80 * 1.25 = 100 USD
    assert posting.units.currency == 'USD'
    assert posting.units.number == Decimal('100')
    assert 'convert_to' not in (posting.meta or {})
    assert posting.meta['converted_from'] == '80 EUR'


def test_currency_convert_no_price_error():
    """Test error handling when no price is available."""
    entries = [
        Transaction(
            meta={},
            date=date(2024, 1, 1),
            flag='*',
            payee=None,
            narration='Test no price',
            tags=set(),
            links=set(),
            postings=[
                Posting(
                    account='Assets:Cash',
                    units=Amount(Decimal('100'), 'EUR'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={'convert_to': 'JPY'}
                )
            ]
        )
    ]
    
    options_map = {}
    
    # Run the plugin
    new_entries, errors = currency_convert(entries, options_map)
    
    # Check that an error was generated
    assert len(errors) == 1
    assert 'No price found' in errors[0].message
    assert 'EUR to JPY' in errors[0].message
    
    # Check that the original posting was kept unchanged
    transactions = [e for e in new_entries if isinstance(e, Transaction)]
    assert len(transactions) == 1
    
    transaction = transactions[0]
    posting = transaction.postings[0]
    
    # Original posting should be unchanged
    assert posting.units.currency == 'EUR'
    assert posting.units.number == Decimal('100')
    assert posting.meta.get('convert_to') == 'JPY'


def test_currency_convert_multiple_postings():
    """Test conversion with multiple postings in the same transaction."""
    entries = [
        # Price data
        Price(
            meta={},
            date=date(2024, 1, 1),
            currency='EUR',
            amount=Amount(Decimal('1.2'), 'USD')
        ),
        Price(
            meta={},
            date=date(2024, 1, 1),
            currency='GBP',
            amount=Amount(Decimal('1.3'), 'USD')
        ),
        # Transaction with multiple postings to convert
        Transaction(
            meta={},
            date=date(2024, 1, 1),
            flag='*',
            payee=None,
            narration='Test multiple conversions',
            tags=set(),
            links=set(),
            postings=[
                Posting(
                    account='Assets:Cash:EUR',
                    units=Amount(Decimal('100'), 'EUR'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={'convert_to': 'USD'}
                ),
                Posting(
                    account='Assets:Cash:GBP',
                    units=Amount(Decimal('50'), 'GBP'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={'convert_to': 'USD'}
                ),
                Posting(
                    account='Expenses:Test',
                    units=Amount(Decimal('-185'), 'USD'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta=None
                )
            ]
        )
    ]
    
    options_map = {}
    
    # Run the plugin
    new_entries, errors = currency_convert(entries, options_map)
    
    # Check for no errors
    assert len(errors) == 0
    
    # Find the modified transaction
    transactions = [e for e in new_entries if isinstance(e, Transaction)]
    assert len(transactions) == 1
    
    transaction = transactions[0]
    
    # Check first posting (EUR to USD)
    first_posting = transaction.postings[0]
    assert first_posting.units.currency == 'USD'
    assert first_posting.units.number == Decimal('120')  # 100 * 1.2
    assert 'convert_to' not in (first_posting.meta or {})
    assert first_posting.meta['converted_from'] == '100 EUR'
    
    # Check second posting (GBP to USD)
    second_posting = transaction.postings[1]
    assert second_posting.units.currency == 'USD'
    assert second_posting.units.number == Decimal('65')  # 50 * 1.3
    assert 'convert_to' not in (second_posting.meta or {})
    assert second_posting.meta['converted_from'] == '50 GBP'
    
    # Check third posting (unchanged)
    third_posting = transaction.postings[2]
    assert third_posting.units.currency == 'USD'
    assert third_posting.units.number == Decimal('-185')


def test_converted_from_metadata():
    """Test that converted_from metadata is correctly added to converted postings."""
    entries = [
        # Price data
        Price(
            meta={},
            date=date(2024, 1, 1),
            currency='EUR',
            amount=Amount(Decimal('1.25'), 'USD')
        ),
        # Transaction with convert_to metadata and additional metadata
        Transaction(
            meta={},
            date=date(2024, 1, 1),
            flag='*',
            payee=None,
            narration='Test converted_from metadata',
            tags=set(),
            links=set(),
            postings=[
                Posting(
                    account='Assets:Cash',
                    units=Amount(Decimal('200'), 'EUR'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={'convert_to': 'USD', 'some_other_meta': 'value'}
                )
            ]
        )
    ]
    
    options_map = {}
    
    # Run the plugin
    new_entries, errors = currency_convert(entries, options_map)
    
    # Check for no errors
    assert len(errors) == 0
    
    # Find the modified transaction
    transactions = [e for e in new_entries if isinstance(e, Transaction)]
    assert len(transactions) == 1
    
    transaction = transactions[0]
    posting = transaction.postings[0]
    
    # Check that the posting was converted
    assert posting.units.currency == 'USD'
    assert posting.units.number == Decimal('250')  # 200 * 1.25
    
    # Check metadata
    assert 'convert_to' not in (posting.meta or {})
    assert posting.meta['converted_from'] == '200 EUR'
    assert posting.meta['some_other_meta'] == 'value'  # Other metadata should be preserved


def test_converted_from_metadata_with_decimals():
    """Test that converted_from metadata preserves decimal precision."""
    entries = [
        # Price data
        Price(
            meta={},
            date=date(2024, 1, 1),
            currency='EUR',
            amount=Amount(Decimal('1.234567'), 'USD')
        ),
        # Transaction with convert_to metadata
        Transaction(
            meta={},
            date=date(2024, 1, 1),
            flag='*',
            payee=None,
            narration='Test decimal precision in converted_from',
            tags=set(),
            links=set(),
            postings=[
                Posting(
                    account='Assets:Cash',
                    units=Amount(Decimal('100.123456'), 'EUR'),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={'convert_to': 'USD'}
                )
            ]
        )
    ]
    
    options_map = {}
    
    # Run the plugin
    new_entries, errors = currency_convert(entries, options_map)
    
    # Check for no errors
    assert len(errors) == 0
    
    # Find the modified transaction
    transactions = [e for e in new_entries if isinstance(e, Transaction)]
    assert len(transactions) == 1
    
    transaction = transactions[0]
    posting = transaction.postings[0]
    
    # Check metadata preserves original amount with precision
    assert posting.meta['converted_from'] == '100.123456 EUR'
