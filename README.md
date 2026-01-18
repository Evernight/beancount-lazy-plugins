# beancount-lazy-plugins
Set of plugins for lazy (or not so) people used by [lazy-beancount](https://github.com/Evernight/lazy-beancount) (but can also be useful on their own).

## Installation
```pip3 install git+https://github.com/Evernight/beancount-lazy-plugins```

## Plugins
* [valuation](#valuation): track total value of the opaque fund over time
* [filter_map](#filter_map): apply operations to group of transactions selected by Fava filters
* [group_pad_transactions](#group_pad_transactions): improves treatment of pad/balance operations for multi-currency accounts
* [balance_extended](#balance_extended): adds extended balance assertions (full, padded, full-padded)
* [pad_extended](#pad_extended): adds pad operation (pad-ext) extending the original pad operation (pad)
* [auto_accounts](#auto_accounts): insert Open directives for accounts not opened
* [generate_base_ccy_prices](#generate_base_ccy_prices): generate base currency prices for all currencies in the ledger (based on the original from [tariochbctools](https://github.com/tarioch/beancounttools/blob/master/src/tariochbctools/plugins/generate_base_ccy_prices.py
))
* [generate_inverse_prices](#generate_inverse_prices): generate inverse price directives for all existing prices
* [currency_convert](#currency_convert): convert posting amounts to different currencies using price data
* [expense_merchant_map](#expense_merchant_map): extend expense account names to include merchant names
* [tag_from_continuous_events](#tag_from_continuous_events): apply tags to transactions based on Events

## valuation
A Beancount plugin to track total value of the opaque fund. You can use it instead of the ```balance``` operation to assert total value of the account. If the value of the account is currently different, it will instead alter price of the underlying synthetical commodity created by the plugin used for technical purposes.

You can use it instead of combination of ```pad```/```balance``` checks to avoid generating realized gains/losses in the account.

### Usage
Enable plugin in the ledger

    plugin "beancount_lazy_plugins.valuation"

Then using a set of ```1970-01-01 custom "valuation" "config"``` commands configure accounts with the opaque funds with following arguments:
1. Account name
2. The corresponding commodity name. These don't really matter and are just for your own reference.
3. A PnL (profits and losses) account that will be used to track realized gains and losses.

```
1970-01-01 custom "valuation" "config"
  account: "Assets:FirstOpaqueFund:Total"
  currency: "OPF1_EUR"
  pnlAccount: "Income:FirstOpaqueFund:Total:PnL"

1970-01-01 custom "valuation" "config"
  account: "Assets:SecondOpaqueFund:Total"
  currency: "OPF2_USD"
  pnlAccount: "Income:SecondOpaqueFund:Total:PnL"
```

Then you can define sample points in time of the total account value using

    2024-01-05 custom "valuation" Assets:FirstOpaqueFund:Total           2345 EUR

Note that multiple currencies per account are not supported.

You can use the fund accounts in transactions as usual, just make sure that only one currency per account is used.
The total fund value will be correctly shown in all operations / Fava interfaces.

You can use one `balance` statement to define initial balance of the account but it has to be before you define 
transactions in/out of the account.

### Example

    1970-01-01 open Assets:CoolFund:Total "FIFO"
    1970-01-01 open Income:CoolFund:PnL

    plugin "beancount_lazy_plugins.valuation"
    1970-01-01 custom "valuation" "config"
        account: "Assets:CoolFund:Total"
        currency: "COOL_FUND_USD"
        pnlAccount: "Income:CoolFund:PnL"

    2024-01-10 * "Investing $1k in CoolFund"
        Assets:Physical:Cash    -1000.00 USD
        Assets:CoolFund:Total    1000.00 USD

    ; CoolFund value falls, COOL_FUND_USD now worth 0.9 USD
    2024-02-10 custom "valuation" Assets:CoolFund:Total 900 USD

    ; CoolFund value falls, COOL_FUND_USD now worth 1.1 USD
    2024-03-11 custom "valuation" Assets:CoolFund:Total 1100 USD

    ; Withdraw 500 USD, after which 600 USD remains which corresponds to 545.45455
    ; in COOL_FUND_USD (still worth 1.1 USD) ???
    2024-03-13 * "Withdraw $500 from CoolFund"
        Assets:Physical:Cash    500.00 USD
        Assets:CoolFund:Total  -500.00 USD

    ; Effectively this gets converted to
    ; 2024-03-13 * "Withdraw $500 from CoolFund"
    ;   Assets:Physical:Cash    500.00 USD
    ;   Assets:CoolFund:Total  -454.55 COOL_FUND_USD {} @ 1.1 USD
    ;   Income:CoolFund:PnL

    ; remaining amount grows to 700 USD
    2024-04-11 custom "valuation" Assets:CoolFund:Total 700 USD

    ; withdraw all
    2024-04-15 * "Withdraw $700 from CoolFund"
        Assets:Physical:Cash    700.00 USD
        Assets:CoolFund:Total  -700.00 USD

    ; Account is at 0 again now

## filter_map
A plugin that allows to apply operations to group of transactions. You can filter by set of parameters (taken from [Fava's filters](https://lazy-beancount.xyz/docs/stage2_expenses/advanced_fava/#filters), plugin is using the same code) and apply tag or add metadata to the transaction. Considering that tags and metadata can later be used by other plugins, it allows a lot of flexibility in the potential usage.

### Syntax
```
2021-01-01 custom "filter-map" "apply"
    ; following three arguments correspond to Fava's filters:
    ; time, account and advanced filter (as ordered left to right in the UI)
    time: "2024-01-09 to 2024-02-15"
    account: "Expenses:Bills"
    filter: "payee:'Company ABCDE' -any(account:'Expenses:Taxes')"
    ; the following arguments specify operations to apply to selected transactions
    ; space-separated list of tags to add (# is optional) to selected transactions
    addTags: "tag1 tag2 #tag3"
    ; any dictionary of the metadata to add/alter selected transactions
    addMeta: "{'comment': 'Transaction description'}" 
```
Beancount entry date can be arbitrary and is not being used by the plugin.

### Example 1: adding tag to all transactions related to certain account
```
2021-01-01 custom "filter-map" "apply"
    account: "Expenses:Bills"
    addTags: "recurring"
```

This will add ```#recurring``` tag to all transactions affecting ```Expenses:Bills```. This may be useful in conjunction with [fava-dashboards](https://github.com/andreasgerstmayr/fava-dashboards)

### Example 2: add tag and comment to recurring expense to a certain account
```
2021-01-01 custom "filter-map" "apply"
    filter: "narration:'WEBSITE.COM/BILL'"
    addTags: "recurring"
    addMeta: "{'comment': 'Montly payment for Service ABCDE'}"
```

Besides adding a tag, add a clarifying comment.

### Example 3: tag all transactions from a specific trip
```
2021-01-01 custom "filter-map" "apply"
    time: "2024-03-12 to 2024-03-23"
    filter: "-#recurring -any(account:'Expenses:Unattributed')"
    addTags: "#trip-country1-24 #travel"
```

Similar to ```pushtag```/```poptag``` operations but much more flexible and, besides, will work alongside all included files and independently of the order in which transactions are defined. Again, useful in combination with [fava-dashboards](https://github.com/andreasgerstmayr/fava-dashboards) (or [lazy-beancount](https://github.com/Evernight/lazy-beancount) where dashboard configs are slightly changed).

### Example 4: advanced usage
```
2021-01-01 custom "filter-map" "apply"
    filter: "#subscription-year"
    addTags: "recurring"
    addMeta: "{'split': '12 months / month'}"
```

Can be used in combination with the [beancount_interpolate](https://github.com/Akuukis/beancount_interpolate) plugin (see Split plugin in particular).

### Example 5: presets
```
2021-01-01 custom "filter-map" "preset"
    name: "trip"
    filter: "-#not-travel -#recurring -any(account:'Expenses:Taxes') -any(account:'Expenses:Unattributed')"

2021-01-01 custom "filter-map" "apply"
    preset: "trip"
    time: "2024-03-15 to 2024-03-22"
    addTags: "#trip-somewhere-24 #travel"
```

Let's consider example 3 again. For each trip you want to describe it's likely that the filter field is going to be the same. To avoid repeating it for all trips you can save it (or any combination of fields, really) to reuse as a preset in other filters. 

### Example 6: renaming/mapping unclear merchant names
```
2021-01-01 custom "filter-map" "apply"
    filter: "payee:'SomeService.*'"
    setPayee: "Some Service"

2021-01-01 custom "filter-map" "apply"
    filter: "payee:'SmService Llc.*'"
    setPayee: "Some Service"
```
When some of the auto-imported merchant names do not make sense or are displayed differently in different transactions or banks, you may map them to something more understandable for you and useful for search / grouping in Fava and dashboards.

## auto_accounts
A Beancount plugin that automatically inserts Open directives for accounts not opened (at the date of the first entry). Slightly improved version of the plugin supplied with Beancount by default. Reports all auto-opened accounts and adds metadata to Open directives. This allows to have the convenience of auto-opening accounts but avoiding accidental mistakes in the ledger.

Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.auto_accounts"
```

You can optionally configure the plugin to avoid reporting certain accounts in a warning using a regex pattern:

```
plugin "beancount_lazy_plugins.auto_accounts" "{'ignore_regex': 'Assets:.*:Pending'}"
```

- **Auto-insertion**: When an account is used in a transaction but doesn't have an Open directive, the plugin automatically creates one at the date of the first entry for that account.
- **Warning generation**: The plugin generates warnings listing all auto-inserted accounts, which helps you review what was automatically added.
- **Account filtering**: You can use the `ignore_regex` configuration to exclude certain accounts from reporting
- **Metadata marking**: Auto-inserted Open directives are marked with `auto_accounts: True` metadata for easy identification.

## currency_convert
A Beancount plugin that automatically converts posting amounts to different currencies based on `convert_to` metadata. This plugin processes all transactions and converts postings that have a `convert_to: "<target_currency>"` metadata field using the price data available in your ledger.
This may be useful if you're adding/modifying transactions manually and when it's easier to specify it in one currency whereas it would make more sense to have it in another currency in the ledger.

### Usage
Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.currency_convert"
```

Then add `convert_to` metadata to any posting you want to convert:

### Example
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

## expense_merchant_map
A Beancount plugin that automatically extends expense account names to include merchant names derived from transaction payees or narrations. This helps create more detailed (but rough) expense categorization by merchant while maintaining your existing high-level expense account structure. May be useful as a quick experiment.

### Usage
Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.expense_merchant_map"
```

It probably doesn't make sense to keep it on all the time, but could be fun as a quick experiment

## group_pad_transactions
This plugin improves treatment of pad/balance operations, in partucular if you use them following
this guide: https://lazy-beancount.xyz/docs/stage1_totals/explanation/

If you have multiple currencies in the single account, multiple pad transactions will be generated.
However, if some of these correspond to currency conversions that you don't specify explicitly
(and I think that's way too much hassle), the groups of pad operations may create too much noise when
you look at transaction journal and tables. This plugin combines these groups into a single transaction.

Enable processing ```pad``` and ```balance``` operations explicitly in the beginning of the ledger:
```
option "plugin_processing_mode" "raw"
```

In the end of the main ledger use plugins in the following order:
```
plugin "beancount.ops.pad"
plugin "beancount.ops.balance"

plugin "beancount_lazy_plugins.group_pad_transactions"
```

## generate_inverse_prices
A Beancount plugin that automatically generates inverse price directives for all existing prices in your ledger.

### Usage
Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.generate_inverse_prices"
```

### Example
If your ledger contains:
```
2024-01-01 price USD 0.85 EUR
2024-01-15 price USD 0.87 EUR
```

The plugin will automatically generate the inverse prices:
```
2024-01-01 price EUR 1.176470588 USD
2024-01-15 price EUR 1.149425287 USD
```

## balance_extended
A Beancount plugin that adds custom balance operations with a type parameter. It helps you:
- **full**: Expand a balance assertion into separate per-currency assertions. For currencies declared in the account's `open` directive but not listed in the custom, a zero balance assertion is generated.
- **padded**: Creates a `pad` directive on day-1 from a specified pad account, and asserts only the currencies explicitly listed in the directive (does not expand to all declared currencies).
- **full-padded**: Combines both behaviors.

### Usage
Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.balance_extended"
```

The balance check with ```balance-ext``` looks like this:
```
2015-01-01 custom "balance-ext" [balance_type] Assets:Bank:Savings  100 EUR  230 USD
```

The ```balance_type``` is optional (default value is configured in the plugin) and is one of the following:

```
; 1) regular — resolves to regular balance check
2015-01-01 custom "balance-ext" "regular" Assets:Bank:Savings  100 EUR  230 USD

; 2) full — per-currency balance assertions; missing declared currencies default to 0
2015-01-01 custom "balance-ext" "full" Assets:Bank:Savings  100 EUR  230 USD

; 3) padded — generates `pad` on previous day from a pad account; asserts only explicitly listed currencies
2015-01-01 custom "balance-ext" "padded" Assets:Bank:Savings Equity:Opening-Balances  100 EUR  230 USD

; 4) full-padded — combines full and padded
2015-01-01 custom "balance-ext" "full-padded" Assets:Bank:Savings Equity:Opening-Balances  100 EUR  230 USD
```

By default "padded" operations generate ```pad-ext``` entries (see below). If you want to use standard ```pad``` operation, you can configure the plugin to do so by setting `default_pad_type` option to `pad`.

The balance type can be specified in a shorter form:
```
2015-01-01 custom "balance-ext" "F" Assets:Bank:Savings  100 EUR  230 USD
2015-01-01 custom "balance-ext" "~" Assets:Bank:Savings  100 EUR  230 USD
2015-01-01 custom "balance-ext" "F~" Assets:Bank:Savings  100 EUR  230 USD
2015-01-01 custom "balance-ext" "~F" Assets:Bank:Savings  100 EUR  230 USD
```

```F``` stands for full, ```~``` stands for padded (```!``` or empty string resolves to regular balance check)

## pad_extended
A Beancount plugin that extends standard pad operation.
1. Pad operation does not generate errors on unused pad entries by default (configurable with `generate_errors_on_unused_pad_entries` option)
2. You can configure default pad account for a set of accounts specified by regular expression.
3. You can override the pad account by adding `pad_account` metadata to the pad entry.

### Usage
Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.pad_extended" "{
    'default_pad_account': [
        (re.compile(r'Assets:Bank:.*'), 'Equity:Opening-Balances'),
    ],
    'generate_errors_on_unused_pad_entries': False,
}
```

Then use it like:

```
2015-01-01 custom "pad-ext" Assets:Bank:Savings
2015-01-05 balance Assets:Bank:Savings 100 EUR
```

## tag_from_continuous_events
A Beancount plugin that automatically applies tags to continuous events. Description of the event directive form the official documentation: https://beancount.github.io/docs/beancount_language_syntax.html#events
The plugin will go through the transactions in the ledger and apply tags accordingly to the value of the event at the date of the transaction. 

### Usage
Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.tag_from_continuous_events"
2021-01-01 custom "tag-from-continuous-events" "config"
    ; optionally specify filters for transactions, like in filter_map plugin. Only transactions matching the filter will be tagged.
    ; account: "Expenses:Food"
    ; filter: "any(account:'Expenses:Food')"
    name: "location"
    tags: "location-{value}"
```

Tag is defined as a string template with one variable {value} that will be replaced with the value of the event at the date of the transaction.

### Example
```
2024-01-01 event "location" "London"
2024-05-03 event "location" "Bangkok"
2024-09-11 event "location" "Berlin"

2024-02-10 * "Coffee"
  Assets:Cash          -3 GBP
  Expenses:Food

2024-07-20 * "Museum tickets"
  Assets:Cash          -25 GBP
  Expenses:Entertainment
```

After running Beancount with the plugin enabled, the transactions will have tags applied based on the active event value at the transaction date:

```
2024-02-10 * "Coffee" #location-London
  Assets:Cash          -3 GBP
  Expenses:Food

2024-07-20 * "Museum tickets" #location-Bangkok
  Assets:Cash          -25 GBP
  Expenses:Entertainment
```
