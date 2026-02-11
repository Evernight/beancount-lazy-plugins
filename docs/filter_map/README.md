# filter_map

A plugin that allows to apply operations to group of transactions. You can filter by set of parameters (taken from [Fava's filters](https://lazy-beancount.xyz/docs/stage2_expenses/advanced_fava/#filters), plugin is using the same code) and apply tag or add metadata to the transaction. Considering that tags and metadata can later be used by other plugins, it allows a lot of flexibility in the potential usage.

## Syntax

```
2021-01-01 custom "filter-map" "apply"
    ; following three arguments correspond to Fava's filters:
    ; time, account and advanced filter (as ordered left to right in the UI)
    time: "2024-01-09 to 2024-02-15"
    account: "Expenses:Bills"
    filter: "payee:'Company ABCDE' -any(account:'Expenses:Taxes')"
    ; the following arguments specify operations to apply to selected transactions
    ; space-separated list of tags to add (# is optional) to selected transactions
    addTags: "tag1 tag2 #tag3"
    ; any dictionary of the metadata to add/alter selected transactions
    addMeta: "{'comment': 'Transaction description'}" 
```

Beancount entry date can be arbitrary and is not being used by the plugin.

## Example 1: adding tag to all transactions related to certain account

```
2021-01-01 custom "filter-map" "apply"
    account: "Expenses:Bills"
    addTags: "recurring"
```

This will add `#recurring` tag to all transactions affecting `Expenses:Bills`. This may be useful in conjunction with [fava-dashboards](https://github.com/andreasgerstmayr/fava-dashboards)

## Example 2: add tag and comment to recurring expense to a certain account

```
2021-01-01 custom "filter-map" "apply"
    filter: "narration:'WEBSITE.COM/BILL'"
    addTags: "recurring"
    addMeta: "{'comment': 'Montly payment for Service ABCDE'}"
```

Besides adding a tag, add a clarifying comment.

## Example 3: tag all transactions from a specific trip

```
2021-01-01 custom "filter-map" "apply"
    time: "2024-03-12 to 2024-03-23"
    filter: "-#recurring -any(account:'Expenses:Unattributed')"
    addTags: "#trip-country1-24 #travel"
```

Similar to `pushtag`/`poptag` operations but much more flexible and, besides, will work alongside all included files and independently of the order in which transactions are defined. Again, useful in combination with [fava-dashboards](https://github.com/andreasgerstmayr/fava-dashboards) (or [lazy-beancount](https://github.com/Evernight/lazy-beancount) where dashboard configs are slightly changed).

## Example 4: advanced usage

```
2021-01-01 custom "filter-map" "apply"
    filter: "#subscription-year"
    addTags: "recurring"
    addMeta: "{'split': '12 months / month'}"
```

Can be used in combination with the [beancount_interpolate](https://github.com/Akuukis/beancount_interpolate) plugin (see Split plugin in particular).

## Example 5: presets

```
2021-01-01 custom "filter-map" "preset"
    name: "trip"
    filter: "-#not-travel -#recurring -any(account:'Expenses:Taxes') -any(account:'Expenses:Unattributed')"

2021-01-01 custom "filter-map" "apply"
    preset: "trip"
    time: "2024-03-15 to 2024-03-22"
    addTags: "#trip-somewhere-24 #travel"
```

Let's consider example 3 again. For each trip you want to describe it's likely that the filter field is going to be the same. To avoid repeating it for all trips you can save it (or any combination of fields, really) to reuse as a preset in other filters.

## Example 6: renaming/mapping unclear merchant names

```
2021-01-01 custom "filter-map" "apply"
    filter: "payee:'SomeService.*'"
    setPayee: "Some Service"

2021-01-01 custom "filter-map" "apply"
    filter: "payee:'SmService Llc.*'"
    setPayee: "Some Service"
```

When some of the auto-imported merchant names do not make sense or are displayed differently in different transactions or banks, you may map them to something more understandable for you and useful for search / grouping in Fava and dashboards.
