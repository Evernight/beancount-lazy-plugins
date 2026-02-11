# pad_extended

_(Experimental, APIs might change slightly in the future)_

A Beancount plugin that extends standard pad operation.

1. Pad operation does not generate errors on unused pad entries by default (configurable with `generate_errors_on_unused_pad_entries` option)
2. Specifying pad account is now not necessary. You can configure default pad account for a set of accounts specified by regular expression.
3. You can override / specify the pad account explicitly by adding `pad_account` metadata to the pad entry.

## Usage

Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.pad_extended" "{
    'default_pad_account': [
        (re.compile(r'Assets:Bank:.*'), 'Equity:Opening-Balances'),
    ],
    'generate_errors_on_unused_pad_entries': False,
    'handle_default_pad_directives': False,
}
```

Then use it like you would use a pad operation normally

```
2015-01-01 custom "pad-ext" Assets:Bank:Savings
2015-01-05 balance Assets:Bank:Savings 100 EUR
```

(or use `balance-ext` with `padded` balance type from [balance_extended](../balance_extended/README.md) plugin).

By default it doesn't handle default Pad operations so you will need to use it alongside `beancount.ops.pad` plugin. If you want it to process default Pad operations as well, set `handle_default_pad_directives` option to True.

You can configure default pad account for a set of accounts specified by regular expression as below:

```
2015-01-01 custom "pad-ext" "config"
  account_regex: "Assets:Bank:.*"
  pad_account: "Expenses:Unattributed:{name}"
```

An account specified in `pad_account` will be used for all padded accounts matching regular expression. Account name is split into `type:name`, so `Assets:Bank:Savings` will be padded with `Expenses:Unattributed:Bank:Savings` in this example. And `{type}` would be replaced with `Assets` if it was present in the configuration.

Since padding can be either positive or negative, you can alternatively specify different pad accounts for positive and negative padding by adding `pad_account_expenses` and `pad_account_income` metadata to the configuration entry:

```
2015-01-01 custom "pad-ext" "config"
  account_regex: "Assets:Bank:.*"
  pad_account_expenses: "Expenses:Unattributed:{name}"
  pad_account_income: "Income:Unattributed:{name}"
```

This will avoid negative expense or positive income postings in the generated pad transactions.

The later configuration directive appears in the file, the more priority it will have for mapping in case account name matches multiple regular expressions. A pad account specified directly on the `pad-ext` entry `pad_account` metadata has the highest priority.
