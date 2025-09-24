# beancount-lazy-plugins
Set of plugins for lazy (or not so) people used by [lazy-beancount](https://github.com/Evernight/lazy-beancount) (but can also be useful on their own).

## Installation
```pip3 install git+https://github.com/Evernight/beancount-lazy-plugins```

## Plugins
* [valuation](#valuation): track total value of the opaque fund over time
* [filter_map](#filter_map): apply operations to group of transactions selected by Fava filters
* [group_pad_transactions](#group_pad_transactions): improves treatment of pad/balance operations for multi-currency accounts
* [auto_accounts](#auto_accounts): automatically insert Open directives for accounts not opened
* [generate_base_ccy_prices](#generate_base_ccy_prices): generate base currency prices for all currencies in the ledger (based on the original from [tariochbctools](https://github.com/tarioch/beancounttools/blob/master/src/tariochbctools/plugins/generate_base_ccy_prices.py
))
* [currency_convert](#currency_convert): convert posting amounts to different currencies using price data
* [expense_merchant_map](#expense_merchant_map): automatically extend expense account names to include merchant names

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
Expenses:Food            120.00 USD
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