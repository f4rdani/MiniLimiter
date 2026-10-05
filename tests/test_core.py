"""Unit tests for MiniLimiter core components."""

import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.models import Rule
from src.core.rules_manager import RulesManager
from src.core.token_bucket import TokenBucket
from src.utils.formatters import format_bytes, format_rate, parse_rate_string


class TestFormatters(unittest.TestCase):
    def test_format_rate(self):
        self.assertEqual(format_rate(500), "500 B/s")
        self.assertEqual(format_rate(1024), "1,00 KB/s")
        self.assertEqual(format_rate(2 * 1024 * 1024), "2,00 MB/s")

    def test_format_bytes(self):
        self.assertEqual(format_bytes(100), "100 B")
        self.assertEqual(format_bytes(1024 * 1024), "1,00 MB")

    def test_parse_rate_string(self):
        self.assertEqual(parse_rate_string("2 MB/s"), 2 * 1024 * 1024)
        self.assertEqual(parse_rate_string("2 MB"), 2 * 1024 * 1024)
        self.assertEqual(parse_rate_string("512 KB/s"), 512 * 1024)
        self.assertEqual(parse_rate_string("1.5 MB/s"), int(1.5 * 1024 * 1024))
        self.assertEqual(parse_rate_string("2"), 2 * 1024 * 1024)


class TestTokenBucket(unittest.TestCase):
    def test_consume_within_capacity(self):
        bucket = TokenBucket(rate_bytes_per_sec=1024 * 1024)  # 1 MB/s
        delay = bucket.consume(1024)
        self.assertEqual(delay, 0.0)

    def test_consume_exceeding_capacity(self):
        bucket = TokenBucket(rate_bytes_per_sec=1000)
        # Drain all tokens
        bucket.tokens = 0
        delay = bucket.consume(500)
        # To get 500 tokens at 1000/s requires 0.5s
        self.assertAlmostEqual(delay, 0.5, delta=0.05)


class TestRulesManager(unittest.TestCase):
    def test_rules_persistence(self):
        with TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "rules.json"
            mgr = RulesManager(config_file)

            rule = Rule(app_name="chrome.exe", limit_in=2 * 1024 * 1024, enabled=True)
            mgr.set_rule(rule)

            # Read back from same instance
            saved = mgr.get_rule("chrome.exe")
            self.assertIsNotNone(saved)
            self.assertEqual(saved.limit_in, 2 * 1024 * 1024)

            # Read from fresh instance
            mgr2 = RulesManager(config_file)
            saved2 = mgr2.get_rule("chrome.exe")
            self.assertIsNotNone(saved2)
            self.assertEqual(saved2.limit_in, 2 * 1024 * 1024)

            # Delete
            mgr2.remove_rule("chrome.exe")
            self.assertIsNone(mgr2.get_rule("chrome.exe"))


if __name__ == "__main__":
    unittest.main()
