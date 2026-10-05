"""Traffic Engine: single divert handle = ukur + limit di satu titik (exactly-once).

Desain lama memakai DUA handle (sniffer priority 0 + shaper priority 10) sehingga
satu paket berisiko dihitung dua kali (7,3 MB/s vs 4,0 MB/s di NetLimiter).
Desain baru: SATU handle divert "!loopback and !impostor and (tcp or udp)" dua arah.
Setiap paket: parse -> catat ke tracker -> cek blocker -> token bucket global
(device limit) -> token bucket per-app -> reinject. Yang diukur = yang dilewatkan,
persis seperti yang dilihat speedtest.

Filter dua arah juga mengaktifkan UL limit/block yang sebelumnya mati
(filter lama hanya "inbound").
"""

import ctypes
import logging
import threading
import time
from typing import Dict, Optional

from src.core.divert_bindings import (
    INVALID_HANDLE_VALUE,
    WINDIVERT_ADDRESS,
    WINDIVERT_LAYER_NETWORK,
    load_windivert_dll,
    parse_packet_detail,
)
from src.core.rules_manager import RulesManager
from src.core.token_bucket import TokenBucket
from src.core.tracker import NetworkTracker

logger = logging.getLogger("MiniLimiter.Shaper")

# Dua arah (in+out), tanpa loopback & tanpa paket reinject sendiri.
DIVERT_FILTER = "!loopback and !impostor and (tcp or udp)"


class TrafficShaper:
    """Single-handle measure-and-shape engine."""

    def __init__(self, tracker: NetworkTracker, rules_mgr: RulesManager):
        self.tracker = tracker
        self.rules_mgr = rules_mgr

        self.dll = load_windivert_dll()
        self._is_running = False

        self.handle = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Token buckets: global (device "-") + per-app
        self._global_dl: Optional[TokenBucket] = None
        self._global_ul: Optional[TokenBucket] = None
        self._dl_buckets: Dict[str, TokenBucket] = {}
        self._ul_buckets: Dict[str, TokenBucket] = {}
        self._bucket_lock = threading.Lock()

        # Kompatibilitas: atribut lama tetap ada (tidak dipakai lagi)
        self.sniff_handle = None
        self.shaper_handle = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def _get_or_create_bucket(self, app_name: str, rate: int, is_inbound: bool) -> TokenBucket:
        with self._bucket_lock:
            buckets = self._dl_buckets if is_inbound else self._ul_buckets
            if app_name not in buckets:
                buckets[app_name] = TokenBucket(rate_bytes_per_sec=rate)
            else:
                buckets[app_name].update_rate(rate)
            return buckets[app_name]

    def _get_global_bucket(self, rate: int, is_inbound: bool) -> TokenBucket:
        with self._bucket_lock:
            if is_inbound:
                if self._global_dl is None:
                    self._global_dl = TokenBucket(rate_bytes_per_sec=rate)
                else:
                    self._global_dl.update_rate(rate)
                return self._global_dl
            else:
                if self._global_ul is None:
                    self._global_ul = TokenBucket(rate_bytes_per_sec=rate)
                else:
                    self._global_ul.update_rate(rate)
                return self._global_ul

    def start(self) -> None:
        """Starts interception (measure + shape)."""
        if self._is_running:
            return

        if not self.dll:
            raise FileNotFoundError("WinDivert.dll not found in bin/ directory.")

        c_filter = DIVERT_FILTER.encode("ascii")
        self.handle = self.dll.WinDivertOpen(c_filter, WINDIVERT_LAYER_NETWORK, 0, 0)

        if not self.handle or self.handle == INVALID_HANDLE_VALUE:
            self.handle = None
            err = ctypes.GetLastError()
            if err == 5:
                raise PermissionError("WinDivert requires Administrator privileges (Error 5: Access Denied).")
            elif err == 2:
                raise FileNotFoundError("WinDivert driver file (WinDivert64.sys) not found (Error 2).")
            else:
                raise RuntimeError(f"WinDivertOpen failed with error: {err}")

        # Kompat: shaper_handle menunjuk handle yang sama
        self.shaper_handle = self.handle

        self._is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="WinDivertEngine", daemon=True)
        self._thread.start()
        logger.info("TrafficShaper engine started (single divert handle, both directions).")

    def stop(self) -> None:
        """Stops interception and closes the WinDivert handle."""
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()

        if self.handle and self.handle != INVALID_HANDLE_VALUE:
            try:
                self.dll.WinDivertClose(self.handle)
            except Exception as e:
                logger.debug(f"WinDivertClose: {e}")
            self.handle = None
            self.shaper_handle = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        logger.info("TrafficShaper engine stopped.")

    def _loop(self) -> None:
        """Measure + enforce untuk setiap paket (exactly-once)."""
        packet_buf = ctypes.create_string_buffer(65535)
        addr = WINDIVERT_ADDRESS()
        read_len = ctypes.c_uint(0)
        write_len = ctypes.c_uint(0)
        recv_fn = self.dll.WinDivertRecv
        send_fn = self.dll.WinDivertSend
        handle = self.handle

        # Cache status rules 500ms agar tidak lock+scan per paket
        last_rule_check = 0.0
        cached_has_rules = False

        while self._is_running:
            # URUTAN BENAR: Recv(handle, buf, buflen, &read_len, &addr)
            if not recv_fn(handle, packet_buf, 65535, ctypes.byref(read_len), ctypes.byref(addr)):
                if not self._is_running:
                    break
                time.sleep(0.001)
                continue

            pkt_len = read_len.value
            if pkt_len <= 0 or pkt_len > 65535:
                continue

            def _reinject():
                # URUTAN BENAR: Send(handle, buf, len, &write_len, &addr)
                try:
                    send_fn(handle, packet_buf, pkt_len, ctypes.byref(write_len), ctypes.byref(addr))
                except Exception:
                    pass

            if addr.is_impostor:
                _reinject()
                continue

            raw = packet_buf.raw[:pkt_len]
            detail = parse_packet_detail(raw, addr.is_ipv6)
            if not detail:
                _reinject()
                continue

            _proto, src_port, dst_port, src_ip, dst_ip = detail
            is_inbound = not addr.is_outbound
            local_port = dst_port if is_inbound else src_port
            remote_ip = src_ip if is_inbound else dst_ip

            # 0. Catat dulu (pra-enforcement) agar rate terlihat walau di-throttle.
            #    Paket yang di-DROP blocker tidak dicatat (sesuai NetLimiter).
            now_chk = time.perf_counter()
            if (now_chk - last_rule_check) > 0.5:
                cached_has_rules = self.rules_mgr.has_any_limiting()
                last_rule_check = now_chk
            limiter_on = self.rules_mgr.master_limiter_enabled
            blocker_on = self.rules_mgr.master_blocker_enabled

            app_name = self.tracker.get_app_for_port(local_port)
            rule = self.rules_mgr.get_rule(app_name) if (app_name and limiter_on) else None
            gl = self.rules_mgr.get_global_limit()

            # 1. Blocker: global dulu, lalu per-app. DROP = tidak reinject & tidak catat.
            # Blocker On mengendalikan SEMUA blocking; Limiter On mengendalikan limit.
            if blocker_on:
                g_block = (gl["block_in"] if is_inbound else gl["block_out"])
                if g_block:
                    continue
                if rule and rule.enabled:
                    if (is_inbound and rule.block_in) or (not is_inbound and rule.block_out):
                        continue

            # 2. Catat byte yang benar-benar dilewatkan (post-block, pre-throttle).
            self.tracker.record_traffic(local_port, pkt_len, is_inbound, remote_ip)

            if not cached_has_rules or not limiter_on:
                _reinject()
                continue

            # 3. Global (device) limit — dibagikan seluruh traffic satu arah.
            total_delay = 0.0
            g_rate = gl["limit_in"] if is_inbound else gl["limit_out"]
            if g_rate and g_rate > 0:
                bucket = self._get_global_bucket(g_rate, is_inbound)
                total_delay += bucket.consume(pkt_len)

            # 4. Per-app limit.
            if rule and rule.enabled:
                limit_rate = rule.limit_in if is_inbound else rule.limit_out
                if limit_rate and limit_rate > 0:
                    bucket = self._get_or_create_bucket(app_name, limit_rate, is_inbound)
                    total_delay += bucket.consume(pkt_len)

            if total_delay > 0:
                time.sleep(min(0.2, total_delay))

            _reinject()
