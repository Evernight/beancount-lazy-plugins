# model_portfolio

A Beancount plugin that generates model portfolio purchase transactions from a single directive. Given a target distribution of assets and a time schedule, the plugin looks up commodity prices from the price map and creates buy transactions at each scheduled date.

## Usage

Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.model_portfolio"
```

## Directive format

```
DATE custom "model-portfolio" "generate"
  distribution: "LIST_OF_TUPLES"
  time: "DURATION / STEP"
  type: "simple"
  source_account: "ACCOUNT"
  amount: "NUMBER CURRENCY"
  description: "NARRATION"
  addTags: "#TAG1, #TAG2"
```

### Fields

| Field | Required | Description |
|---|---|---|
| `distribution` | yes | Python literal list of `(account, commodity, fraction)` tuples. Fractions should sum to 1.0. |
| `time` | yes | Time specification in `beancount_interpolate` format: `DURATION / STEP`. See below. |
| `type` | yes | Currently only `"simple"` is supported (split amount proportionally). |
| `source_account` | yes | Account to debit the total amount from. |
| `amount` | yes | Total purchase amount per period, e.g. `"2000 USD"`. |
| `description` | no | Transaction narration. Defaults to `"Model portfolio purchase"`. |
| `addTags` | no | Comma-separated tags to add to generated transactions, e.g. `"#model_portfolio, #virtual"`. |

### Time specification

The `time` field uses the same format as `beancount_interpolate`'s recur plugin:

```
[N] PERIOD / [M] STEP
```

- `N PERIOD` — total duration (e.g. `2 years`, `6 months`, `90 days`)
- `M STEP` — interval between transactions (e.g. `1 month`, `2 weeks`)

Transactions are generated from `DATE` up to (but not including) `DATE + DURATION`, one per step. Dates beyond today are skipped.

**Examples:**
- `"2 years / 2 months"` — every 2 months for 2 years (12 transactions)
- `"1 year / 1 month"` — monthly for one year (12 transactions)
- `"6 months / 2 weeks"` — every 2 weeks for 6 months

## Example

```beancount
2020-01-01 custom "model-portfolio" "generate"
  distribution: "[
    ('Assets:Portfolio:VWRP', 'VWRP', 0.8)
    ('Assets:Portfolio:BNDW', 'BNDW', 0.2)
  ]"
  time: "2 years / 2 months"
  type: "simple"
  source_account: "Assets:Investment:Cash"
  amount: "2000 USD"
  description: "Generated transaction for model portfolio"
  addTags: "#model_portfolio, #virtual"
```

Given price entries `VWRP: 99.50 USD` and `BNDW: 82.10 USD` on 2020-01-01, the plugin generates:

```beancount
2020-01-01 * "Generated transaction for model portfolio" #model_portfolio #virtual
  Assets:Portfolio:VWRP  16.08040201 VWRP {99.50 USD}
  Assets:Portfolio:BNDW   4.87087699 BNDW {82.10 USD}
  Assets:Investment:Cash  -2000 USD
```

The same transaction shape is repeated for 2020-03-01, 2020-05-01, … up to 2021-11-01, each time using the price closest to that date from the price map.

## Notes

- The `custom` directive is consumed by the plugin and does not appear in the output.
- If no price is found for a commodity on a given date, a `ModelPortfolioError` is emitted and that date's transaction is skipped.
- Asset units are rounded to 8 decimal places using banker's rounding (`ROUND_HALF_EVEN`). The resulting rounding error per transaction is well within beancount's default tolerance of `0.005 USD`.
- Generated transactions carry `generated_by: "model_portfolio"` metadata.
- Cost basis is recorded using `{price CURRENCY}` syntax, enabling proper lot tracking for capital gains calculations.
