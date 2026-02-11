# auto_accounts

A Beancount plugin that automatically inserts Open directives for accounts not opened (at the date of the first entry). Slightly improved version of the plugin supplied with Beancount by default. Reports all auto-opened accounts and adds metadata to Open directives. This allows to have the convenience of auto-opening accounts but avoiding accidental mistakes in the ledger.

## Usage

Enable the plugin in your ledger:

```
plugin "beancount_lazy_plugins.auto_accounts"
```

You can optionally configure the plugin to avoid reporting certain accounts in a warning using a regex pattern:

```
plugin "beancount_lazy_plugins.auto_accounts" "{'ignore_regex': 'Assets:.*:Pending'}"
```

- **Auto-insertion**: When an account is used in a transaction but doesn't have an Open directive, the plugin automatically creates one at the date of the first entry for that account.
- **Warning generation**: The plugin generates warnings listing all auto-inserted accounts, which helps you review what was automatically added.
- **Account filtering**: You can use the `ignore_regex` configuration to exclude certain accounts from reporting
- **Metadata marking**: Auto-inserted Open directives are marked with `auto_accounts: True` metadata for easy identification.
