# generate_inverse_prices

A Beancount plugin that automatically generates inverse price directives for all existing prices in your ledger.

## Usage

Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.generate_inverse_prices"
```

## Example

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
