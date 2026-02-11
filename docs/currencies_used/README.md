# currencies_used

A Beancount plugin that tracks currencies used per account and adds metadata to Open directives. This helps you identify which currencies are used in which accounts.
With `extend_open_directives` option set to True, it will also extend Open directives with the currencies used. This is useful, for example, in combination with [balance_extended](../balance_extended/README.md) plugin (full balance check) to avoid specifying currencies manually.

## Usage

Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.currencies_used"
```

Or with optional configuration:

```
plugin "beancount_lazy_plugins.currencies_used" "{
    'extend_open_directives': True,
    'extend_from_pad_directives': True,
}"
```
