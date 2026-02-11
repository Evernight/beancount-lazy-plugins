# generate_base_ccy_prices

A Beancount plugin that generates base currency prices for all currencies in the ledger. Based on the original from [tariochbctools](https://github.com/tarioch/beancounttools/blob/master/src/tariochbctools/plugins/generate_base_ccy_prices.py).

The plugin inserts additional price directives by applying foreign exchange rates to convert existing prices to the ledger's base currency.
