"""
A Beancount plugin that automatically applies tags to transactions based on Events.

This plugin supports "continuous events" (see Beancount's Event directive). For a given
event variable name (e.g. "location"), it finds the latest Event on or before the date
of each transaction and applies tags derived from that event's value.

Configuration is provided via a Custom directive:

  YYYY-MM-DD custom "tag-from-continuous-events" "config"
      name: "location"
      tags: "location-{value}"

The "tags" field may contain multiple space-separated tag templates. Each template may
use "{value}" which will be replaced with the event value. The resulting tags are
added without the leading "#".
"""

from __future__ import annotations

import collections
import dataclasses
from bisect import bisect_right
from typing import Any, Iterable, Optional

from beancount.core import data
from beancount.core.data import Custom, Event, Transaction
from fava.core.fava_options import FavaOptions
from fava.core.filters import AccountFilter, AdvancedFilter, TimeFilter

__plugins__ = ["tag_from_continuous_events"]


TagFromContinuousEventsError = collections.namedtuple(
    "TagFromContinuousEventsError", "source message entry"
)


@dataclasses.dataclass(frozen=True)
class _Config:
    event_name: str
    tag_templates: tuple[str, ...]
    time: Optional[str] = None
    account: Optional[str] = None
    filter: Optional[str] = None


def _parse_tag_templates(tags_value: str) -> tuple[str, ...]:
    # Allow specifying either "#tag" or "tag" templates; split on whitespace.
    parts = [part.strip() for part in tags_value.split() if part.strip()]
    return tuple(part.lstrip("#") for part in parts)


def _iter_configs(entries: Iterable[data.Directive]) -> tuple[list[_Config], list]:
    configs: list[_Config] = []
    errors: list = []

    for entry in entries:
        if not isinstance(entry, Custom):
            continue
        if entry.type != "tag-from-continuous-events":
            continue
        if not entry.values or str(entry.values[0].value).strip() != "config":
            continue

        name = entry.meta.get("name") if entry.meta else None
        tags_value = entry.meta.get("tags") if entry.meta else None
        time_value = entry.meta.get("time") if entry.meta else None
        account_value = entry.meta.get("account") if entry.meta else None
        filter_value = entry.meta.get("filter") if entry.meta else None

        if not isinstance(name, str) or not name.strip():
            errors.append(
                TagFromContinuousEventsError(
                    source=entry.meta or {},
                    message='Missing or invalid "name" in config custom directive',
                    entry=entry,
                )
            )
            continue
        if not isinstance(tags_value, str) or not tags_value.strip():
            errors.append(
                TagFromContinuousEventsError(
                    source=entry.meta or {},
                    message='Missing or invalid "tags" in config custom directive',
                    entry=entry,
                )
            )
            continue

        if time_value is not None and (not isinstance(time_value, str) or not time_value.strip()):
            errors.append(
                TagFromContinuousEventsError(
                    source=entry.meta or {},
                    message='Invalid "time" in config custom directive; expected a non-empty string',
                    entry=entry,
                )
            )
            continue
        if account_value is not None and (
            not isinstance(account_value, str) or not account_value.strip()
        ):
            errors.append(
                TagFromContinuousEventsError(
                    source=entry.meta or {},
                    message='Invalid "account" in config custom directive; expected a non-empty string',
                    entry=entry,
                )
            )
            continue
        if filter_value is not None and (
            not isinstance(filter_value, str) or not filter_value.strip()
        ):
            errors.append(
                TagFromContinuousEventsError(
                    source=entry.meta or {},
                    message='Invalid "filter" in config custom directive; expected a non-empty string',
                    entry=entry,
                )
            )
            continue

        templates = _parse_tag_templates(tags_value)
        if not templates:
            errors.append(
                TagFromContinuousEventsError(
                    source=entry.meta or {},
                    message='"tags" must contain at least one tag template',
                    entry=entry,
                )
            )
            continue

        configs.append(
            _Config(
                event_name=name.strip(),
                tag_templates=templates,
                time=time_value.strip() if isinstance(time_value, str) else None,
                account=account_value.strip() if isinstance(account_value, str) else None,
                filter=filter_value.strip() if isinstance(filter_value, str) else None,
            )
        )

    return configs, errors


def _matches_filter(entry: Transaction, filter_obj: Any) -> bool:
    """Match using Fava filter semantics (kept consistent with filter_map plugin)."""
    if isinstance(filter_obj, TimeFilter):
        return entry.date >= filter_obj.date_range.begin and entry.date < filter_obj.date_range.end
    return len(filter_obj.apply([entry])) > 0


def _build_event_timeline(
    entries: Iterable[data.Directive],
) -> dict[str, list[tuple[data.datetime.date, str]]]:
    timeline: dict[str, list[tuple[data.datetime.date, str]]] = collections.defaultdict(list)

    for entry in entries:
        if isinstance(entry, Event):
            timeline[entry.type].append((entry.date, entry.description))

    # Input should be already chronological but make this robust.
    for event_name, changes in timeline.items():
        changes.sort(key=lambda dv: dv[0])
        timeline[event_name] = changes

    return dict(timeline)


def _value_at(
    changes: list[tuple[data.datetime.date, str]], on_date: data.datetime.date
) -> Optional[str]:
    if not changes:
        return None
    dates = [d for d, _ in changes]
    idx = bisect_right(dates, on_date) - 1
    if idx < 0:
        return None
    return changes[idx][1]


def tag_from_continuous_events(entries, options_map, config_str=None):
    """Apply tags to transactions based on continuous event values."""
    configs, errors = _iter_configs(entries)
    if not configs:
        return entries, errors

    compiled_filters: dict[_Config, list[Any]] = {}
    for cfg in configs:
        filters: list[Any] = []
        try:
            if cfg.time:
                filters.append(TimeFilter(options_map, FavaOptions(), cfg.time))
            if cfg.account:
                filters.append(AccountFilter(cfg.account))
            if cfg.filter:
                filters.append(AdvancedFilter(cfg.filter))
        except Exception as exc:
            errors.append(
                TagFromContinuousEventsError(
                    source={},
                    message=(
                        f"Failed to build filters for event {cfg.event_name!r}: {exc}. "
                        'Check "time", "account", and "filter" in the config.'
                    ),
                    entry=None,
                )
            )
            filters = []
        compiled_filters[cfg] = filters

    timeline = _build_event_timeline(entries)

    new_entries: list[data.Directive] = []
    for entry in entries:
        if not isinstance(entry, Transaction):
            new_entries.append(entry)
            continue

        current_tags = set(entry.tags or data.EMPTY_SET)
        new_tags = set(current_tags)

        for cfg in configs:
            filters = compiled_filters.get(cfg, [])
            if filters and not all(_matches_filter(entry, f) for f in filters):
                continue

            changes = timeline.get(cfg.event_name)
            if not changes:
                continue
            value = _value_at(changes, entry.date)
            if value is None:
                continue

            for tmpl in cfg.tag_templates:
                try:
                    tag = tmpl.format(value=value)
                except Exception as exc:
                    errors.append(
                        TagFromContinuousEventsError(
                            source=entry.meta or {},
                            message=f"Failed to format tag template {tmpl!r}: {exc}",
                            entry=entry,
                        )
                    )
                    continue
                tag = tag.strip().lstrip("#")
                if tag:
                    new_tags.add(tag)

        if new_tags != current_tags:
            new_entries.append(
                Transaction(
                    meta=entry.meta,
                    date=entry.date,
                    flag=entry.flag,
                    payee=entry.payee,
                    narration=entry.narration,
                    tags=frozenset(new_tags),
                    links=entry.links,
                    postings=entry.postings,
                )
            )
        else:
            new_entries.append(entry)

    return new_entries, errors


