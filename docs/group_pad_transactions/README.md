# group_pad_transactions

This plugin improves treatment of pad/balance operations, in particular if you use them following
[this guide](https://lazy-beancount.xyz/docs/stage1_totals/explanation/).

If you have multiple currencies in the single account, multiple pad transactions will be generated.
However, if some of these correspond to currency conversions that you don't specify explicitly
(and I think that's way too much hassle), the groups of pad operations may create too much noise when
you look at transaction journal and tables. This plugin combines these groups into a single transaction.

## Usage

Enable processing `pad` and `balance` operations explicitly in the beginning of the ledger:

```
option "plugin_processing_mode" "raw"
```

In the end of the main ledger use plugins in the following order:

```
plugin "beancount.ops.pad"
plugin "beancount.ops.balance"

plugin "beancount_lazy_plugins.group_pad_transactions"
```
