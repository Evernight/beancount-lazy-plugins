"""
Tests for the valuation plugin functionality.
"""
import pytest
import io
from pathlib import Path
from decimal import Decimal
from datetime import date

from beancount import loader
from beancount.core.data import Amount, Balance, Booking, Commodity, Open, Price, Transaction
from beancount.parser import printer
from beancount_lazy_plugins.valuation import valuation


@pytest.mark.parametrize(
    "test_file,test_id",
    [
        pytest.param("cool_fund_example.beancount", "cool_fund", id="cool_fund"),
        pytest.param("some_fund_example.beancount", "some_fund", id="some_fund"),
    ],
)
def test_valuation_plugin(test_file, test_id, capture_output):
    """Test the valuation plugin with different example files.
    
    Args:
        test_file: The name of the test file to use
        test_id: Identifier for the test case
        capture_output: If True, write the processed file to tests/data/output.
                       If False, compare the test results with the expected output.
    """
    # Define paths
    data_dir = Path("tests") / "data"
    input_path = data_dir / test_file
    output_dir = data_dir / "output"
    ref_path = output_dir / f"{test_id}_output.beancount"

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load ledger file
    entries, errors, options_map = loader.load_file(str(input_path))
    if errors:
        pytest.fail(f"Failed to load test ledger: {errors}")

    # No need to run the plugin as it's already run by the loader
    # # Run the valuation plugin
    # new_entries, plugin_errors = valuation(entries, options_map)
    # if plugin_errors:
    #     pytest.fail(f"Plugin errors: {plugin_errors}")
    new_entries = entries
    
    # Run test-specific assertions
    if test_id == "cool_fund":
        assert_cool_fund_example(new_entries)
    elif test_id == "some_fund":
        assert_some_fund_example(new_entries)
    
    # Handle output based on capture_output option
    if capture_output:
        # Write the output to a file
        with open(ref_path, "w") as f:
            printer.print_entries(new_entries, file=f)
    else:
        # Compare with reference file if it exists
        if ref_path.exists():
            with open(ref_path, "r") as f:
                expected_output = f.read()
            
            actual_output = None
            # Convert new_entries to string for comparison
            with io.StringIO() as output:
                printer.print_entries(new_entries, file=output)
                actual_output = output.getvalue()
            
            assert actual_output == expected_output, "Output does not match expected output"
        else:
            pytest.skip("Reference file does not exist. Run with --capture-output to create it.")


def assert_cool_fund_example(new_entries):
    """Assert specific conditions for the cool_fund_example.beancount test."""
    # 1. Check that the COOL_FUND_USD commodity was created
    cool_fund_commodity = None
    for entry in new_entries:
        if isinstance(entry, Commodity) and entry.currency == "COOL_FUND_USD":
            cool_fund_commodity = entry
            break
    assert cool_fund_commodity is not None, "COOL_FUND_USD commodity was not created"
    
    # 2. Check that price entries were created for each valuation
    price_entries = [entry for entry in new_entries if isinstance(entry, Price) and entry.currency == "COOL_FUND_USD"]
    
    # Check the specific price values based on the comments in the file
    # First valuation: COOL_FUND_USD worth 0.9 USD
    price_2024_02_10 = next((entry for entry in price_entries if entry.date == date(2024, 2, 10)), None)
    assert price_2024_02_10 is not None, "Price entry for 2024-02-10 not found"
    assert price_2024_02_10.amount == Amount(Decimal("0.9"), "USD"), "Incorrect price for 2024-02-10"
    
    # Second valuation: COOL_FUND_USD worth 1.1 USD
    price_2024_03_11 = next((entry for entry in price_entries if entry.date == date(2024, 3, 11)), None)
    assert price_2024_03_11 is not None, "Price entry for 2024-03-11 not found"
    assert price_2024_03_11.amount == Amount(Decimal("1.1"), "USD"), "Incorrect price for 2024-03-11"
    
    # Third valuation: COOL_FUND_USD worth 1.28333333 USD (700/545.(45))
    price_2024_04_11 = next((entry for entry in price_entries if entry.date == date(2024, 4, 11)), None)
    assert price_2024_04_11 is not None, "Price entry for 2024-04-11 not found"
    assert abs(price_2024_04_11.amount.number - Decimal("1.28333333")) < Decimal("0.0001"), "Incorrect price for 2024-04-11"
    
    # 3. Check that the transactions were modified correctly
    modified_transactions = [entry for entry in new_entries if isinstance(entry, Transaction)]
    assert len(modified_transactions) >= 3, f"Expected at least 3 modified transactions, got {len(modified_transactions)}"
    
    # 4. Check that the PnL account was used in the modified transactions
    pnl_postings = []
    for entry in modified_transactions:
        for posting in entry.postings:
            if posting.account == "Income:CoolFund:PnL":
                pnl_postings.append(posting)
    assert len(pnl_postings) > 0, "No PnL postings were created"
    
    # 5. Check that the COOL_FUND_USD currency is used in the modified transactions
    cool_fund_postings = []
    for entry in modified_transactions:
        for posting in entry.postings:
            if posting.account == "Assets:CoolFund:Total" and posting.units.currency == "COOL_FUND_USD":
                cool_fund_postings.append(posting)
    assert len(cool_fund_postings) > 0, "No COOL_FUND_USD postings were created"


def assert_some_fund_example(new_entries):
    pass


def test_creates_open_when_missing_in_ledger():
    ledger = """
option "operating_currency" "USD"

1970-01-01 open Assets:Physical:Cash
1970-01-01 open Income:CoolFund:PnL

1970-01-01 custom "valuation" "config"
    account: "Assets:CoolFund:Total"
    currency: "COOL_FUND_USD"
    pnlAccount: "Income:CoolFund:PnL"

2024-01-10 * "Investing $1k in CoolFund"
    Assets:Physical:Cash    -1000.00 USD
    Assets:CoolFund:Total    1000.00 USD
"""

    entries, _, options_map = loader.load_string(ledger)

    new_entries, errors = valuation(entries, options_map)
    assert not errors

    opens = [e for e in new_entries if isinstance(e, Open)]
    open_entry = next((e for e in opens if e.account == "Assets:CoolFund:Total"), None)
    assert open_entry is not None, "Expected an Open entry for Assets:CoolFund:Total to be created"
    assert open_entry.currencies == ["COOL_FUND_USD"]
    assert open_entry.booking == Booking.FIFO
    