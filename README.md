# beancount-lazy-plugins
Set of plugins used by [lazy-beancount](https://github.com/Evernight/lazy-beancount) (but can also be useful on their own).

## Installation
```pip3 install git+https://github.com/Evernight/beancount-lazy-plugins```

## Plugins
* [valuation](#valuation): track total value of the opaque fund ovre time
* [filter_map](#filter_map): apply operations to group of transactions selected by Fava filters
* [group_pad_transactions](#group_pad_transactions): improves treatment of pad/balance operations for multi-currency accounts

## valuation
A Beancount plugin to track total value of the opaque fund. You can use it instead of the ```balance``` operation to assert total value of the account. If the value of the account is currently different, it will instead alter price of the underlying synthetical commodity created by the plugin used for technical purposes.

You can use it instead of combination of ```pad```/```balance``` checks to avoid generating realized gains/losses in the account.

### Usage
Enable plugin in the ledger

    plugin "beancount_lazy_plugins.valuation"

Then using a set of ```1970-01-01 custom "valuation" "config"``` commands configure accounts with the opaque funds with following arguments:
1. Accouny name
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
A plugin that allows to apply operations to group of transactions. You can filter by selectors (taken from Fava's selectors and using the same code) and apply tag or add metadata to the transaction. Considering that metadata can later be used by other plugins that allows a lot of flexibility of the possible usage

### Syntax
```
2021-01-01 custom "filter-map" "apply"
    time: "2024-01-09 to 2024-02-15" ; same as Fava's time filter
    account: "Expenses:Bills" ; same as Fava's account
    filter: "payee:'Company ABCDE' -any(account:'Expenses:Taxes')" ; same as Fava's advanced filter field
    addTags: "tag1 tag2 #tag3" ; space-separated list of tags to add (# is optional) to selected transactions
    addMeta: "{'comment': 'Transaction description'}" ; any dictionary of the metadata to add/alter selected transactions
```
Operation date is arbitrary and not being used by the plugin

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

Similar to ```pushtag```/```poptag``` operations but much more flexible and, besides, will work alongside all included files and independently of the order in which transactions are defined. Again, useful in combination with ```fava-dashboards``` (and [lazy-beancount](https://github.com/Evernight/lazy-beancount) with slightly modified dashboard configs).

### Example 4: advanced usage
```
2021-01-01 custom "filter-map" "apply"
    filter: "#subscription-year"
    addTags: "recurring"
    addMeta: "{'split': '12 months / month'}"
```

Can be used in combination with the [beancount_interpolate](https://github.com/Akuukis/beancount_interpolate) plugin (see Split plugin in particular).

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
