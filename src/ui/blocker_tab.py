"""Deprecated shim: tab Blocker sudah digabung ke Rules (RuleListTab + filter).

File ini dipertahankan agar import lama & test lama tidak rusak.
Gunakan `RuleListTab` dengan `set_filter("Blocker")` sebagai gantinya.
"""

from src.ui.rule_list_tab import RuleListTab  # noqa: F401


class BlockerTab(RuleListTab):
    """Alias backward-compat: RuleListTab yang langsung terfilter Blocker."""

    def __init__(self, master, on_rule_selected=None, **kwargs):
        def _noop_delete(_app_name):
            return None

        def _noop_toggle(_app_name, _enabled=None):
            return None

        super().__init__(
            master,
            on_delete_rule=kwargs.pop("on_delete_rule", _noop_delete),
            on_toggle_rule=kwargs.pop("on_toggle_rule", _noop_toggle),
            on_rule_selected=on_rule_selected,
            **kwargs,
        )
        try:
            self.set_filter("Blocker")
        except Exception:
            pass
