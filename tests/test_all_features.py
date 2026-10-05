"""Comprehensive unit tests covering all features and components of MiniLimiter."""

import ctypes
import os
import struct
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.divert_bindings import (
    WINDIVERT_ADDRESS,
    WINDIVERT_FLAG_SNIFF,
    parse_packet_ports,
)
from src.core.models import ProcessInfo, Rule
from src.core.rules_manager import RulesManager
from src.core.shaper import TrafficShaper
from src.core.token_bucket import TokenBucket
from src.core.tracker import NetworkTracker
from src.utils.formatters import format_bytes, format_rate, parse_rate_string


class TestFormatters(unittest.TestCase):
    """Tests for unit formatting and parsing."""

    def test_format_rate_autobyte(self):
        self.assertEqual(format_rate(0), "0 B/s")
        self.assertEqual(format_rate(-50), "0 B/s")
        self.assertEqual(format_rate(512), "512 B/s")
        self.assertEqual(format_rate(1024), "1,00 KB/s")
        self.assertEqual(format_rate(1536), "1,50 KB/s")
        self.assertEqual(format_rate(2 * 1024 * 1024), "2,00 MB/s")
        self.assertEqual(format_rate(1.98 * 1024 * 1024), "1,98 MB/s")
        self.assertEqual(format_rate(1024 * 1024 * 1024), "1,00 GB/s")

    def test_format_rate_locked_units(self):
        # Locked KB/s
        self.assertEqual(format_rate(0, unit_mode="KB/s"), "0,00 KB/s")
        self.assertEqual(format_rate(2048, unit_mode="KB/s"), "2,00 KB/s")
        self.assertEqual(format_rate(2 * 1024 * 1024, unit_mode="KB/s"), "2048,00 KB/s")

        # Locked MB/s
        self.assertEqual(format_rate(0, unit_mode="MB/s"), "0,00 MB/s")
        self.assertEqual(format_rate(2 * 1024 * 1024, unit_mode="MB/s"), "2,00 MB/s")
        self.assertEqual(format_rate(512 * 1024, unit_mode="MB/s"), "0,50 MB/s")

    def test_format_bytes(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(1024), "1,00 KB")
        self.assertEqual(format_bytes(1024 * 1024), "1,00 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024), "1,00 GB")

    def test_parse_rate_string(self):
        self.assertEqual(parse_rate_string("2 MB/s"), 2 * 1024 * 1024)
        self.assertEqual(parse_rate_string("2mb/s"), 2 * 1024 * 1024)
        self.assertEqual(parse_rate_string("2 MB"), 2 * 1024 * 1024)
        self.assertEqual(parse_rate_string("512 KB/s"), 512 * 1024)
        self.assertEqual(parse_rate_string("1.5 MB/s"), int(1.5 * 1024 * 1024))
        self.assertEqual(parse_rate_string("2"), 2 * 1024 * 1024)
        with self.assertRaises(ValueError):
            parse_rate_string("invalid_speed")


class TestModels(unittest.TestCase):
    """Tests for core data models."""

    def test_rule_serialization(self):
        rule = Rule(
            app_name="Chrome.EXE",
            limit_in=2097152,
            limit_out=1048576,
            block_in=False,
            block_out=True,
            enabled=True,
        )
        d = rule.to_dict()
        self.assertEqual(d["app_name"], "Chrome.EXE")
        self.assertEqual(d["limit_in"], 2097152)
        self.assertEqual(d["block_out"], True)

        restored = Rule.from_dict(d)
        self.assertEqual(restored.app_name, "chrome.exe")  # normalized lowercase
        self.assertEqual(restored.limit_in, 2097152)
        self.assertEqual(restored.limit_out, 1048576)
        self.assertTrue(restored.block_out)
        self.assertTrue(restored.enabled)

    def test_process_info_initialization(self):
        info = ProcessInfo(name="spotify.exe")
        self.assertEqual(info.name, "spotify.exe")
        self.assertEqual(info.dl_rate, 0.0)
        self.assertEqual(info.ul_rate, 0.0)
        self.assertFalse(info.is_online)


class TestTokenBucket(unittest.TestCase):
    """Tests for token bucket bandwidth rate limiter."""

    def test_instant_consumption(self):
        bucket = TokenBucket(rate_bytes_per_sec=2 * 1024 * 1024)
        delay = bucket.consume(1500)
        self.assertEqual(delay, 0.0)

    def test_delay_when_quota_exhausted(self):
        bucket = TokenBucket(rate_bytes_per_sec=10000)
        bucket.tokens = 0
        delay = bucket.consume(5000)
        self.assertAlmostEqual(delay, 0.5, delta=0.02)

    def test_token_refill_over_time(self):
        bucket = TokenBucket(rate_bytes_per_sec=100000)
        bucket.tokens = 0
        time.sleep(0.05)
        delay = bucket.consume(1000)
        self.assertEqual(delay, 0.0)

    def test_update_rate(self):
        bucket = TokenBucket(rate_bytes_per_sec=1000)
        bucket.update_rate(5000)
        self.assertEqual(bucket.rate, 5000)


class TestRulesManager(unittest.TestCase):
    """Tests for rules persistence and management."""

    def test_crud_and_persistence(self):
        with TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "rules.json"
            mgr = RulesManager(cfg)

            rule = Rule(app_name="chrome.exe", limit_in=2097152, enabled=True)
            mgr.set_rule(rule)

            # Retrieve
            retrieved = mgr.get_rule("chrome.exe")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.limit_in, 2097152)

            # Master switch test
            mgr.master_limiter_enabled = False
            mgr.save()

            # Reload fresh instance
            mgr2 = RulesManager(cfg)
            self.assertFalse(mgr2.master_limiter_enabled)
            self.assertEqual(len(mgr2.get_all_rules()), 1)

            # Delete
            mgr2.remove_rule("chrome.exe")
            self.assertIsNone(mgr2.get_rule("chrome.exe"))


class TestNetworkTracker(unittest.TestCase):
    """Tests for port mapping and rate calculations."""

    def test_realistic_streaming_traffic(self):
        tracker = NetworkTracker(scan_interval=0.5)
        tracker._port_to_proc[44333] = ("chrome.exe", 9999)

        # Simulate 100 packets of 1460 bytes arriving over 1 second (146,000 bytes = ~142.5 KB/s)
        for _ in range(100):
            tracker.record_traffic(44333, 1460, is_inbound=True)

        tracker.last_tick_time = time.perf_counter() - 1.0
        tracker._calculate_rates()

        app = tracker.get_app("chrome.exe")
        self.assertIsNotNone(app)
        # Rate must strictly be 146,000 B/s (~142.5 KB/s) - definitely NOT GB/s!
        self.assertAlmostEqual(app.dl_rate, 146000, delta=1000)
        self.assertLess(app.dl_rate, 1024 * 1024)  # Less than 1 MB/s!

    def test_rate_drops_to_zero_instantly_when_idle(self):
        tracker = NetworkTracker(scan_interval=0.5)
        tracker._port_to_proc[55555] = ("testapp.exe", 1234)

        tracker.record_traffic(55555, 50000, is_inbound=True)
        tracker.last_tick_time = time.perf_counter() - 1.0
        tracker._calculate_rates()

        app = tracker.get_app("testapp.exe")
        self.assertEqual(app.total_dl, 50000)

        # In the next tick, NO packets arrive: rate must be EXACTLY 0.0
        tracker.last_tick_time = time.perf_counter() - 1.0
        tracker._calculate_rates()
        self.assertEqual(app.dl_rate, 0.0)
        self.assertEqual(app.total_dl, 50000)


class TestDivertBindings(unittest.TestCase):
    """Tests for packet parser and WinDivert C structs."""

    def test_windivert_sniff_flag_constant(self):
        self.assertEqual(WINDIVERT_FLAG_SNIFF, 1)

    def test_windivert_address_struct_size(self):
        self.assertEqual(ctypes.sizeof(WINDIVERT_ADDRESS), 80)

    def test_bitfields_native(self):
        addr = WINDIVERT_ADDRESS()
        addr.Outbound = 1
        addr.IPv6 = 1
        addr.Impostor = 1
        addr.Loopback = 0

        self.assertTrue(addr.is_outbound)
        self.assertTrue(addr.is_ipv6)
        self.assertTrue(addr.is_impostor)
        self.assertFalse(addr.is_loopback)

    def test_parse_ipv4_tcp_packet(self):
        ip_header = bytearray(20)
        ip_header[0] = 0x45
        ip_header[9] = 6

        tcp_header = bytearray(20)
        struct.pack_into("!HH", tcp_header, 0, 443, 54321)

        packet = bytes(ip_header + tcp_header)
        res = parse_packet_ports(packet, is_ipv6=False)
        self.assertIsNotNone(res)
        proto, src_port, dst_port = res
        self.assertEqual(proto, 6)
        self.assertEqual(src_port, 443)
        self.assertEqual(dst_port, 54321)

    def test_parse_ipv4_udp_packet(self):
        ip_header = bytearray(20)
        ip_header[0] = 0x45
        ip_header[9] = 17

        udp_header = bytearray(8)
        struct.pack_into("!HH", udp_header, 0, 53, 58000)

        packet = bytes(ip_header + udp_header)
        res = parse_packet_ports(packet, is_ipv6=False)
        self.assertIsNotNone(res)
        proto, src_port, dst_port = res
        self.assertEqual(proto, 17)
        self.assertEqual(src_port, 53)
        self.assertEqual(dst_port, 58000)

    def test_parse_invalid_packet(self):
        self.assertIsNone(parse_packet_ports(b"\x45\x00\x00", is_ipv6=False))
        ip_header = bytearray(20)
        ip_header[0] = 0x45
        ip_header[9] = 1
        self.assertIsNone(parse_packet_ports(bytes(ip_header) + b"\x00" * 8, is_ipv6=False))


class TestTrafficShaperLogic(unittest.TestCase):
    """Tests for shaper bucket allocation and lifecycle."""

    def test_bucket_management(self):
        tracker = NetworkTracker()
        with TemporaryDirectory() as tmp:
            mgr = RulesManager(Path(tmp) / "rules.json")
            shaper = TrafficShaper(tracker, mgr)

            bucket1 = shaper._get_or_create_bucket("chrome.exe", 2097152, is_inbound=True)
            self.assertEqual(bucket1.rate, 2097152)

            bucket2 = shaper._get_or_create_bucket("chrome.exe", 1048576, is_inbound=True)
            self.assertIs(bucket1, bucket2)
            self.assertEqual(bucket2.rate, 1048576)


if __name__ == "__main__":
    unittest.main()
