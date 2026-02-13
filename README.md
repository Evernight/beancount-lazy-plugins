# beancount-lazy-plugins

Set of plugins used by [lazy-beancount](https://github.com/Evernight/lazy-beancount). Of course, they can also be installed and used on their own.

![License](https://img.shields.io/badge/license-MIT-green.svg)

## Installation

```bash
pip3 install git+https://github.com/Evernight/beancount-lazy-plugins
```

## Plugins

* [valuation](docs/valuation/README.md) — track total value of the opaque fund over time
* [filter_map](docs/filter_map/README.md) — apply operations to group of transactions selected by Fava filters
* [group_pad_transactions](docs/group_pad_transactions/README.md) — improves treatment of pad/balance operations for multi-currency accounts
* [balance_extended](docs/balance_extended/README.md) — adds extended balance assertions (full, padded, full-padded)
* [pad_extended](docs/pad_extended/README.md) — adds pad operation (pad-ext) extending the original pad operation (pad)
* [auto_accounts](docs/auto_accounts/README.md) — insert Open directives for accounts not opened
* [currencies_used](docs/currencies_used/README.md) — track currencies used per account and add metadata to Open directives
* [generate_base_ccy_prices](docs/generate_base_ccy_prices/README.md) — generate base currency prices for all currencies in the ledger (based on the original from [tariochbctools](https://github.com/tarioch/beancounttools/blob/master/src/tariochbctools/plugins/generate_base_ccy_prices.py))
* [generate_inverse_prices](docs/generate_inverse_prices/README.md) — generate inverse price directives for all existing prices
* [currency_convert](docs/currency_convert/README.md) — convert posting amounts to different currencies using price data
* [expense_merchant_map](docs/expense_merchant_map/README.md) — extend expense account names to include merchant names
* [tag_from_continuous_events](docs/tag_from_continuous_events/README.md) — apply tags to transactions based on Events
