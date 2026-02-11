# expense_merchant_map

A Beancount plugin that automatically extends expense account names to include merchant names derived from transaction payees or narrations. This helps create more detailed (but rough) expense categorization by merchant while maintaining your existing high-level expense account structure. May be useful as a quick experiment.

## Usage

Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.expense_merchant_map"
```

It probably doesn't make sense to keep it on all the time, but could be fun as a quick experiment.
