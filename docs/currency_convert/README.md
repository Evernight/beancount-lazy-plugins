# currency_convert

A Beancount plugin that automatically converts posting amounts to different currencies based on `convert_to` metadata. This plugin processes all transactions and converts postings that have a `convert_to: "<target_currency>"` metadata field using the price data available in your ledger.
This may be useful if you're adding/modifying transactions manually and when it's easier to specify it in one currency whereas it would make more sense to have it in another currency in the ledger.

## Usage

Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.currency_convert"
```

Then add `convert_to` metadata to any posting you want to convert:

## Example

```
; Price data
2024-01-15 price EUR 1.20 USD

2024-01-15 * "Convert EUR expense to USD"
    Assets:Cash:USD         -120.00 USD
    Expenses:Food            100.00 EUR
        convert_to: "USD"
```

After processing, the expense posting becomes:

```
Expenses:Food            120.00 USD @ 1.2 EUR
    converted_from: "100.00 EUR"
```
