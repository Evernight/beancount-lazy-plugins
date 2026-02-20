# pad_extended

A Beancount plugin that extends standard pad operation by replacing it with `pad-ext` custom directives with configurable default options. Differences from standard pad operation:

1. Pad operation does not generate errors on unused pad entries by default (configurable with `generate_errors_on_unused_pad_entries` option)
2. Specifying pad account is not required. You can configure default pad account for a set of accounts specified by regular expression.
3. Different pad account can be automatically assigned depending on the sign of the balance difference and whether it's the first balance assertion for the account (typically the case for ```Equity:OpeningBalances``` account).
4. You can still override / specify the pad account explicitly by adding `pad_account` metadata to the pad entry.

## Usage
The plugin handles both standard `pad` directives and `pad-ext` custom directives, so it replaces `beancount.ops.pad` (do not enable both). Note that to disable automatic ```beancount.ops.pad``` and ```beancount.ops.balance```, you need to set ```option "plugin_processing_mode" "raw"``` option in the beginning of the ledger, like so:

```
option "plugin_processing_mode" "raw"

plugin "beancount_lazy_plugins.pad_extended" "{
    'default_pad_account': [
        ('.*', 'Expenses:Unreconciled:{name}'),
    ],
    'generate_errors_on_unused_pad_entries': False,
}

; Keep balance assertions in place
plugin "beancount.ops.balance"
```

Then use it like you would use a pad operation normally:

```
2015-01-01 custom "pad-ext" Assets:Bank:Savings
2015-01-05 balance Assets:Bank:Savings 100 EUR
```

(or use `balance-ext` with `padded` balance type from [balance_extended](../balance_extended/README.md) plugin).

You can configure default pad account for a set of accounts specified by regular expression as below:

```
2015-01-01 custom "pad-ext" "config"
  account_regex: "Assets:Bank:.*"
  pad_account: "Expenses:Unreconciled:{name}"
```

An account specified in `pad_account` will be used for all padded accounts matching regular expression. Account name is split into `type:name`, so `Assets:Bank:Savings` will be padded with `Expenses:Unreconciled:Bank:Savings` in this example. And `{type}` would be replaced with `Assets` if it was present in the configuration.

Since padding can be either positive or negative, you can alternatively specify different pad accounts for positive and negative padding by adding `pad_account_expenses` and `pad_account_income` metadata to the configuration entry:

```
2015-01-01 custom "pad-ext" "config"
  account_regex: "Assets:Bank:.*"
  pad_account_expenses: "Expenses:Unreconciled:{name}"
  pad_account_income: "Income:Unreconciled:{name}"
```

This will avoid negative expense or positive income postings in the generated pad transactions. However, if you're regularly dealing with multiple currencies and don't want to be having to be very precise with all the conversions, I would recommend to keep only ```Expenses``` pad account and use ```group_pad_transactions``` plugin to group pad transactions. This way a pad that has both -100 EUR and 120 USD postings will be close to 0 when conerted to a single currency and will not demand your attention.

The later configuration directive appears in the file, the more priority it will have for mapping in case account name matches multiple regular expressions. A pad account specified directly on the `pad-ext` entry `pad_account` metadata has the highest priority.

To specify separate account for initial balance, you can add `pad_account_initial` metadata to the configuration entry:
```
2015-01-01 custom "pad-ext" "config"
  account_regex: "Assets:Bank:.*"
  pad_account_expenses: "Expenses:Unreconciled:{name}"
  pad_account_income: "Income:Unreconciled:{name}"
  pad_account_initial: "Equity:Opening-Balances"
```
