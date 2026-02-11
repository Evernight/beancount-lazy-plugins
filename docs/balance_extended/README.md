# balance_extended

_(Experimental, APIs might change slightly in the future)_

A Beancount plugin that adds custom balance operations with a type parameter:

- **full**: Expand a balance assertion into separate per-currency assertions. For currencies declared in the account's `open` directive but not listed in the custom, a zero balance assertion is generated.
- **padded**: Creates a `pad` directive on day-1 from a specified pad account, and asserts only the currencies explicitly listed in the directive (does not expand to all declared currencies).
- **full-padded**: Combines both behaviors.
- **valuation**: Just converts to a `custom "valuation"` entry for the account and amount (see [valuation](../valuation/README.md) plugin).

## Usage

Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.balance_extended"
```

The balance check with `balance-ext` looks like this:

```
2015-01-01 custom "balance-ext" [balance_type] Assets:Bank:Savings  100 EUR  230 USD
```

The `balance_type` is optional (default value is configured in the plugin) and is one of the following:

```
; 1) regular — resolves to regular balance check
2015-01-01 custom "balance-ext" "regular" Assets:Bank:Savings  100 EUR  230 USD

; 2) full — per-currency balance assertions; missing declared currencies default to 0
2015-01-01 custom "balance-ext" "full" Assets:Bank:Savings  100 EUR  230 USD

; 3) padded — generates `pad` on previous day from a pad account; asserts only explicitly listed currencies
2015-01-01 custom "balance-ext" "padded" Assets:Bank:Savings Equity:Opening-Balances  100 EUR  230 USD

; 4) full-padded — combines full and padded
2015-01-01 custom "balance-ext" "full-padded" Assets:Bank:Savings Equity:Opening-Balances  100 EUR  230 USD

; 5) valuation — converts to a `custom "valuation"` entry for the account and amount (see valuation plugin)
2015-01-01 custom "balance-ext" "valuation" Assets:OpaqueFund:Total  2345 EUR
```

By default "padded" operations generate `pad-ext` entries (see [pad_extended](../pad_extended/README.md) plugin). If you want to use standard `pad` operation, you can configure the plugin to use it instead by setting `default_pad_type` option to `pad`.

The balance type can also be specified in a shorter form:

```
2015-01-01 custom "balance-ext" "F" Assets:Bank:Savings  100 EUR  230 USD
2015-01-01 custom "balance-ext" "~" Assets:Bank:Savings  100 EUR  230 USD
2015-01-01 custom "balance-ext" "F~" Assets:Bank:Savings  100 EUR  230 USD
2015-01-01 custom "balance-ext" "~F" Assets:Bank:Savings  100 EUR  230 USD
2015-01-01 custom "balance-ext" "V" Assets:OpaqueFund:Total  2345 EUR
```

where `F` stands for full, `~` stands for padded, `V` stands for valuation, `!` or empty string resolves to regular balance check

You can also set a default balance type per account using configuration directives:

```
2015-01-01 custom "balance-ext" "config"
  account_regex: "Assets:.*"
  balance_type: "full-padded"
```

The last matching configuration directive in the file takes precedence.

There's also an option to specify preferred pad dates in the config:

```
2015-01-01 custom "balance-ext" "config"
  preferred_pad_dates: [1, 15]
```

These dates will be preferred instead of the previous day when generating pad entries, unless it crosses the previous balance entry for that account.
This is useful when you want pad operations to appear on specific dates, for example for more consistent behaviour when using filters in Fava.
