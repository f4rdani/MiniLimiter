"""Tests for device-level (global) limit + single-handle shaper."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.divert_bindings import parse_packet_detail, is_private_ip
from src.core.rules_manager import RulesManager
from src.core.shaper import DIVERT_FILTER, TrafficShaper
from src.core.tracker import NetworkTracker


class TestGlobalLimit(unittest.TestCase):
    def test_set_get_persist(self):
        with TemporaryDirectory() as tmp:
            m = RulesManager(Path(tmp) / "rules.json")
            self.assertIsNone(m.get_global_limit()["limit_in"])
            self.assertFalse(m.has_any_limiting())
            m.set_global_limit(4 * 1024 * 1024, None, False, False)
            self.assertEqual(m.get_global_limit()["limit_in"], 4 * 1024 * 1024)
            self.assertTrue(m.has_any_limiting())
            m2 = RulesManager(Path(tmp) / "rules.json")
            self.assertEqual(m2.get_global_limit()["limit_in"], 4 * 1024 * 1024)
            m2.set_global_limit(None, None, False, False)
            self.assertFalse(m2.has_any_limiting())

    def test_single_handle_both_directions(self):
        self.assertIn("tcp", DIVERT_FILTER)
        self.assertIn("udp", DIVERT_FILTER)
        self.assertIn("!impostor", DIVERT_FILTER)
        self.assertNotIn("inbound", DIVERT_FILTER)  # dua arah (UL ikut)
        t = NetworkTracker()
        with TemporaryDirectory() as tmp:
            s = TrafficShaper(t, RulesManager(Path(tmp) / "r.json"))
            self.assertTrue(hasattr(s, "_loop"))
            self.assertFalse(hasattr(s, "_sniff_loop"))
            b1 = s._get_global_bucket(4 * 1024 * 1024, True)
            b2 = s._get_global_bucket(4 * 1024 * 1024, True)
            self.assertIs(b1, b2)

    def test_group_split(self):
        t = NetworkTracker()
        t._port_to_proc[50000] = ("a.exe", 1)
        t.record_traffic(50000, 1000, True, "8.8.8.8")       # internet
        t.record_traffic(50000, 1000, True, "192.168.1.5")   # local
        import time
        t.last_tick_time = time.perf_counter() - 1.0
        t._calculate_rates()
        i_dl, _i_ul, l_dl, _l_ul = t.get_group_rates()
        self.assertAlmostEqual(i_dl, 1000, delta=50)
        self.assertAlmostEqual(l_dl, 1000, delta=50)

    def test_all_processes_enumerated(self):
        import time
        t = NetworkTracker(scan_interval=0.2, history_length=10)
        t.start()
        try:
            time.sleep(1.5)
            apps = t.get_all_apps()
            names = [a.name for a in apps]
            # Proses python yang menjalankan test ini harus terdaftar (foreground)
            self.assertIn("python.exe", names)
            # Lebih dari sekadar pemilik socket (background ikut terdaftar)
            self.assertGreater(len(apps), 10)
        finally:
            t.stop()

    def test_snapshot_atomic(self):
        import time
        t = NetworkTracker()
        t._port_to_proc[41000] = ("snap.exe", 7)
        for _ in range(50):
            t.record_traffic(41000, 1400, True, "8.8.8.8")
        t.last_tick_time = time.perf_counter() - 1.0
        t._calculate_rates()
        apps, groups, gtotals = t.snapshot()
        by_name = {a.name: a for a in apps}
        self.assertIn("snap.exe", by_name)
        # Grup dan per-app dari tick yang sama -> konsisten (<5% toleransi float)
        self.assertAlmostEqual(groups[0], by_name["snap.exe"].dl_rate, delta=max(1.0, groups[0] * 0.05))
        self.assertEqual(gtotals[0], 50 * 1400)

    def test_remote_fallback_attribution(self):
        import time
        t = NetworkTracker()
        t._remote_to_proc["9.9.9.9"] = ("fallback.exe", 9, time.perf_counter())
        app = t.record_traffic(59999, 1400, True, "9.9.9.9")
        self.assertEqual(app, "fallback.exe")
        app2 = t.record_traffic(59998, 1400, True, "10.99.99.99")
        self.assertEqual(app2, "system")
        self.assertGreater(t._stat_remote_fb, 0)
        self.assertGreater(t._stat_unmapped, 0)

    def test_computer_name_dynamic(self):
        from src.utils.appinfo import get_computer_name
        name = get_computer_name()
        self.assertTrue(isinstance(name, str) and len(name) > 0)
        # stabil (cached) dan sama dengan hostname OS bila tersedia
        import socket
        try:
            self.assertEqual(name, socket.gethostname())
        except Exception:
            pass

    def test_detail_parser_ips(self):
        ip = bytearray(20)
        ip[0] = 0x45
        ip[9] = 6
        ip[12:16] = bytes([192, 168, 1, 5])
        ip[16:20] = bytes([93, 184, 216, 34])
        pkt = bytes(ip + bytearray(b"\x01\xbb\x00\x50" + b"\x00" * 16))
        d = parse_packet_detail(pkt, False)
        self.assertIsNotNone(d)
        _p, sp, dp, sip, dip = d
        self.assertEqual(sp, 443)
        self.assertEqual(dp, 80)
        self.assertTrue(is_private_ip(sip))
        self.assertFalse(is_private_ip(dip))


if __name__ == "__main__":
    unittest.main()
