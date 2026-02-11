# tag_from_continuous_events

A Beancount plugin that automatically applies tags to continuous events. Description of the event directive from the [official documentation](https://beancount.github.io/docs/beancount_language_syntax.html#events).
The plugin will go through the transactions in the ledger and apply tags accordingly to the value of the event at the date of the transaction.

## Usage

Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.tag_from_continuous_events"
2021-01-01 custom "tag-from-continuous-events" "config"
    ; optionally specify filters for transactions, like in filter_map plugin. Only transactions matching the filter will be tagged.
    ; account: "Expenses:Food"
    ; filter: "any(account:'Expenses:Food')"
    name: "location"
    tags: "location-{value}"
```

Tag is defined as a string template with one variable {value} that will be replaced with the value of the event at the date of the transaction.

## Example

```
2024-01-01 event "location" "London"
2024-05-03 event "location" "Bangkok"
2024-09-11 event "location" "Berlin"

2024-02-10 * "Coffee"
  Assets:Cash          -3 GBP
  Expenses:Food

2024-07-20 * "Museum tickets"
  Assets:Cash          -25 GBP
  Expenses:Entertainment
```

After running Beancount with the plugin enabled, the transactions will have tags applied based on the active event value at the transaction date:

```
2024-02-10 * "Coffee" #location-London
  Assets:Cash          -3 GBP
  Expenses:Food

2024-07-20 * "Museum tickets" #location-Bangkok
  Assets:Cash          -25 GBP
  Expenses:Entertainment
```
