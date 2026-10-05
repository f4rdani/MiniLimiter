"""Manager for application rate limiting and blocking rules."""

import json
import logging
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional
from src.core.models import Rule

logger = logging.getLogger("MiniLimiter.RulesManager")


class RulesManager:
    """Thread-safe manager for persisting and querying traffic shaping rules."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._lock = RLock()
        self._rules: Dict[str, Rule] = {}
        self.master_limiter_enabled: bool = True
        self.master_blocker_enabled: bool = True
        # Global device-level limit (root "-" di Activity, seperti NetLimiter).
        # None = tidak dibatasi. Diterapkan ke SELURUH traffic (semua app).
        self.global_limit_in: Optional[int] = None
        self.global_limit_out: Optional[int] = None
        self.global_block_in: bool = False
        self.global_block_out: bool = False
        self.load()

    def get_rule(self, app_name: str) -> Optional[Rule]:
        """Returns the rule for the specified app name, or None (hanya jika enabled)."""
        key = app_name.lower().strip()
        with self._lock:
            rule = self._rules.get(key)
            if rule and rule.enabled:
                return rule
            return None

    def get_rule_any(self, app_name: str) -> Optional[Rule]:
        """Returns rule even if disabled (untuk toggle Enable/Disable & InfoView)."""
        key = app_name.lower().strip()
        with self._lock:
            return self._rules.get(key)

    def get_all_rules(self) -> List[Rule]:
        """Returns copies of all defined rules."""
        with self._lock:
            return list(self._rules.values())

    def set_rule(self, rule: Rule) -> None:
        """Adds or updates a rule for an application and persists to disk."""
        key = rule.app_name.lower().strip()
        with self._lock:
            self._rules[key] = rule
            self.save()

    def remove_rule(self, app_name: str) -> bool:
        """Deletes a rule by application name."""
        key = app_name.lower().strip()
        with self._lock:
            if key in self._rules:
                del self._rules[key]
                self.save()
                return True
            return False

    def set_global_limit(self, limit_in: Optional[int], limit_out: Optional[int] = None,
                         block_in: bool = False, block_out: bool = False) -> None:
        """Set device-level limit (root '-'), persist ke disk."""
        with self._lock:
            self.global_limit_in = limit_in
            self.global_limit_out = limit_out
            self.global_block_in = block_in
            self.global_block_out = block_out
            self.save()

    def get_global_limit(self) -> Dict[str, object]:
        with self._lock:
            return {
                "limit_in": self.global_limit_in,
                "limit_out": self.global_limit_out,
                "block_in": self.global_block_in,
                "block_out": self.global_block_out,
            }

    def has_any_limiting(self) -> bool:
        """True jika ada minimal satu pembatas/blocker aktif (per-app atau global)."""
        with self._lock:
            if self.global_limit_in or self.global_limit_out or self.global_block_in or self.global_block_out:
                return True
            return any(r.enabled and (r.limit_in or r.limit_out or r.block_in or r.block_out)
                       for r in self._rules.values())

    def load(self) -> None:
        """Loads rules from the JSON configuration file."""
        with self._lock:
            if not self.config_path.exists():
                return
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.master_limiter_enabled = data.get("master_limiter_enabled", True)
                    self.master_blocker_enabled = data.get("master_blocker_enabled", True)
                    self.global_limit_in = data.get("global_limit_in")
                    self.global_limit_out = data.get("global_limit_out")
                    self.global_block_in = data.get("global_block_in", False)
                    self.global_block_out = data.get("global_block_out", False)
                    rules_data = data.get("rules", [])
                    self._rules.clear()
                    for r_dict in rules_data:
                        r = Rule.from_dict(r_dict)
                        self._rules[r.app_name] = r
                logger.info(f"Loaded {len(self._rules)} rules from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load rules: {e}", exc_info=True)

    def save(self) -> None:
        """Persists current rules to the JSON configuration file."""
        with self._lock:
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "master_limiter_enabled": self.master_limiter_enabled,
                    "master_blocker_enabled": self.master_blocker_enabled,
                    "global_limit_in": self.global_limit_in,
                    "global_limit_out": self.global_limit_out,
                    "global_block_in": self.global_block_in,
                    "global_block_out": self.global_block_out,
                    "rules": [r.to_dict() for r in self._rules.values()]
                }
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save rules: {e}", exc_info=True)
