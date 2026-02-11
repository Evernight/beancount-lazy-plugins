# valuation

A Beancount plugin to track total value of the opaque fund. You can use it instead of the `balance` operation to assert total value of the account. If the value of the account is currently different, it will instead alter price of the underlying synthetical commodity created by the plugin used for technical purposes.

You can use it instead of combination of `pad`/`balance` checks to avoid generating realized gains/losses in the account.

## Usage

Enable plugin in the ledger

```
plugin "beancount_lazy_plugins.valuation"
```

Then using a set of `1970-01-01 custom "valuation" "config"` commands configure accounts with the opaque funds with following arguments:
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

```
2024-01-05 custom "valuation" Assets:FirstOpaqueFund:Total           2345 EUR
```

Note that multiple currencies per account are not supported.

You can use the fund accounts in transactions as usual, just make sure that only one currency per account is used.
The total fund value will be correctly shown in all operations / Fava interfaces.

You can use one `balance` statement to define initial balance of the account but it has to be before you define 
transactions in/out of the account.

## Example

```
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
```
