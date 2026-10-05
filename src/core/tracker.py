"""Process and Socket Tracker for mapping network packets to applications."""

import logging
import time
from collections import deque
from threading import Event, RLock, Thread
from typing import Dict, List, Optional, Set, Tuple

import psutil

from src.core.models import ProcessInfo

logger = logging.getLogger("MiniLimiter.Tracker")


class NetworkTracker:
    """Monitors active sockets, maps network ports to application names, and calculates real-time bandwidth.

    Realtime design (match Task Manager):
    - Rate tick default 0.5s (Task Manager ~1s, tapi sampling 0.5s terasa realtime).
    - Socket scan (psutil, berat) hanya tiap 1.0s, rate calc tiap tick.
    - Port mapping pakai TTL 10s agar paket untuk port yang baru dibuka/tutup tidak hilang.
    - Traffic yang port-nya tidak dikenal TETAP dihitung ke "system" agar TOTAL sesuai Task Manager.
    - Total NIC via psutil.net_io_counters() selalu dihitung (jalan walau tanpa Admin/WinDivert).
    """

    UNMAPPED_APP = "system"
    PORT_TTL_SECONDS = 10.0
    REMOTE_TTL_SECONDS = 30.0
    # App tanpa socket & tanpa traffic dibuang setelah solange tidak terlihat.
    APP_PRUNE_SECONDS = 300.0

    def __init__(self, scan_interval: float = 0.5, history_length: int = 120,
                 socket_refresh_interval: float = 1.0):
        self.scan_interval = scan_interval
        self.history_length = history_length
        self.socket_refresh_interval = max(scan_interval, socket_refresh_interval)

        self._lock = RLock()
        self._stop_event = Event()

        # Port mapping: local_port -> (app_name_lower, pid)
        self._port_to_proc: Dict[int, Tuple[str, int]] = {}
        self._port_last_seen: Dict[int, float] = {}
        # Fallback attribution: remote_ip -> (app_name_lower, pid, last_seen).
        # Menyelamatkan paket yang local port-nya sudah hilang dari tabel
        # (koneksi pendek/churn) agar tidak jatuh ke "system".
        self._remote_to_proc: Dict[str, Tuple[str, int, float]] = {}
        # Statistik atribusi (untuk anomaly log)
        self._stat_mapped = 0
        self._stat_remote_fb = 0
        self._stat_unmapped = 0

        # PID cache: pid -> (app_name_lower, exe_path)
        self._pid_cache: Dict[int, Tuple[str, str]] = {}

        # Accumulated bytes in the current sampling window
        self._window_bytes_in: Dict[str, int] = {}
        self._window_bytes_out: Dict[str, int] = {}
        # Grup Internet vs LocalNetwork ala NetLimiter (akumulasi window)
        self._window_internet_in: int = 0
        self._window_internet_out: int = 0
        self._window_local_in: int = 0
        self._window_local_out: int = 0
        self.internet_dl_rate: float = 0.0
        self.internet_ul_rate: float = 0.0
        self.local_dl_rate: float = 0.0
        self.local_ul_rate: float = 0.0
        # Kumulatif grup (untuk mode Total di Activity)
        self.total_internet_dl: int = 0
        self.total_internet_ul: int = 0
        self.total_local_dl: int = 0
        self.total_local_ul: int = 0

        # Lifetime stats and current rates per app
        self._apps: Dict[str, ProcessInfo] = {}
        self._app_last_seen: Dict[str, float] = {}

        # Overall and per-app throughput history: deque of (timestamp, dl_rate, ul_rate)
        self.total_history: deque = deque(maxlen=history_length)
        self.app_histories: Dict[str, deque] = {}

        # NIC totals (psutil.net_io_counters) — sumber yang sama dengan Task Manager (Performance tab)
        self.nic_dl_rate: float = 0.0
        self.nic_ul_rate: float = 0.0
        self._nic_last_in: Optional[int] = None
        self._nic_last_out: Optional[int] = None
        self._nic_last_time: Optional[float] = None

        self.last_tick_time = time.perf_counter()
        self._last_socket_refresh = 0.0
        self._worker_thread: Optional[Thread] = None

    def start(self) -> None:
        """Starts the background connection scanner and rate calculator."""
        self._stop_event.clear()
        self.last_tick_time = time.perf_counter()
        self._nic_last_time = self.last_tick_time
        try:
            nic = psutil.net_io_counters()
            self._nic_last_in = nic.bytes_recv
            self._nic_last_out = nic.bytes_sent
        except Exception:
            self._nic_last_in = None
            self._nic_last_out = None
        self._refresh_sockets()
        self._last_socket_refresh = time.perf_counter()
        # Recreate thread agar bisa start/stop berulang (thread hanya bisa start sekali)
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._worker_thread = Thread(target=self._run_loop, name="NetTrackerThread", daemon=True)
            self._worker_thread.start()
        logger.info("NetworkTracker background monitor started.")

    def stop(self) -> None:
        """Stops the background scanner thread."""
        self._stop_event.set()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        logger.info("NetworkTracker stopped.")

    def get_app_for_port(self, port: int) -> Optional[str]:
        """Fast O(1) lookup to find which app name owns the local port."""
        with self._lock:
            proc = self._port_to_proc.get(port)
            return proc[0] if proc else None

    def record_traffic(self, port: int, num_bytes: int, is_inbound: bool, remote_ip: Optional[str] = None) -> Optional[str]:
        """Records byte count for the application using the specified port.

        PENTING: paket dengan port tak dikenal TIDAK dibuang lagi — dicatat ke
        "system" agar TOTAL sesuai Task Manager (sebelumnya return None = hilang).
        remote_ip dipakai untuk split Internet vs LocalNetwork ala NetLimiter.
        Returns the application name (selalu ada, fallback "system").
        """
        # Sanity: paket IP max 65535 byte. Nilai di luar itu = driver glitch
        # (pernah menyebabkan 38 GB/s karena arg WinDivertRecv tertukar).
        if num_bytes <= 0 or num_bytes > 65535:
            return None
        with self._lock:
            proc = self._port_to_proc.get(port)
            if proc:
                app_name = proc[0]
                self._stat_mapped += 1
            else:
                # Fallback: cocokkan via remote IP (koneksi pendek yang
                # local port-nya belum/ sudah tidak ada di tabel).
                fb = self._remote_to_proc.get(remote_ip) if remote_ip else None
                if fb and (time.perf_counter() - fb[2]) < self.REMOTE_TTL_SECONDS:
                    app_name = fb[0]
                    self._stat_remote_fb += 1
                else:
                    app_name = self.UNMAPPED_APP
                    self._stat_unmapped += 1
            if is_inbound:
                self._window_bytes_in[app_name] = self._window_bytes_in.get(app_name, 0) + num_bytes
            else:
                self._window_bytes_out[app_name] = self._window_bytes_out.get(app_name, 0) + num_bytes
            # Klasifikasi grup
            try:
                from src.core.divert_bindings import is_private_ip
                is_local = is_private_ip(remote_ip) if remote_ip else False
            except Exception:
                is_local = False
            if is_local:
                if is_inbound:
                    self._window_local_in += num_bytes
                else:
                    self._window_local_out += num_bytes
            else:
                if is_inbound:
                    self._window_internet_in += num_bytes
                else:
                    self._window_internet_out += num_bytes
            return app_name

    def get_group_rates(self) -> Tuple[float, float, float, float]:
        """(internet_dl, internet_ul, local_dl, local_ul) dalam byte/s."""
        with self._lock:
            return self.internet_dl_rate, self.internet_ul_rate, self.local_dl_rate, self.local_ul_rate

    def _resolve_pid_info(self, pid: int) -> Tuple[str, str]:
        """Cached lookup of process name and executable path."""
        if pid in self._pid_cache:
            return self._pid_cache[pid]
        try:
            p = psutil.Process(pid)
            name = p.name().lower()
            try:
                exe = p.exe()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                exe = name
            self._pid_cache[pid] = (name, exe)
            return name, exe
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return f"pid_{pid}", ""

    def _refresh_sockets(self) -> None:
        """Scans active network connections and updates port-to-process mappings.

        - Port lama dipertahankan selama TTL (10s) agar tidak race dengan paket yang baru tiba.
        - PID 0 / None (kernel/System) dicatat sebagai "system", tidak di-skip.
        """
        try:
            connections = psutil.net_connections(kind="inet")
        except Exception as e:
            logger.warning(f"Error fetching network connections: {e}")
            return

        now = time.perf_counter()
        new_port_map: Dict[int, Tuple[str, int]] = {}
        active_apps: Dict[str, Set[int]] = {}  # app_name -> set of PIDs
        active_ports: Dict[str, Set[int]] = {} # app_name -> set of ports
        live_pids: Set[int] = set()

        for conn in connections:
            if not conn.laddr:
                continue
            lport = conn.laddr.port
            pid = conn.pid or 0
            if pid == 0:
                app_name, exe_path = "system", ""
            else:
                app_name, exe_path = self._resolve_pid_info(pid)
                live_pids.add(pid)
            new_port_map[lport] = (app_name, pid)

            try:
                raddr = getattr(conn, "raddr", None)
                rip = raddr.ip if raddr else ""
                if rip:
                    self._remote_to_proc[rip] = (app_name, pid, now)
            except Exception:
                pass

            active_apps.setdefault(app_name, set()).add(pid)
            active_ports.setdefault(app_name, set()).add(lport)

            with self._lock:
                if app_name not in self._apps:
                    self._apps[app_name] = ProcessInfo(
                        name=app_name,
                        exe_path=exe_path,
                        pids=set(),
                        ports=set(),
                        is_online=True,
                    )
                if exe_path:
                    self._apps[app_name].exe_path = exe_path

        with self._lock:
            # Merge + TTL: pertahankan port lama yang masih segar
            merged = dict(new_port_map)
            for old_port, old_proc in self._port_to_proc.items():
                if old_port not in merged:
                    last = self._port_last_seen.get(old_port, now)
                    if (now - last) < self.PORT_TTL_SECONDS:
                        merged[old_port] = old_proc
            self._port_to_proc = merged
            for p in merged:
                if p in new_port_map:
                    self._port_last_seen[p] = now
                elif p not in self._port_last_seen:
                    self._port_last_seen[p] = now
            # Bersihkan entry yang sudah kedaluwarsa
            expired = [p for p, t in self._port_last_seen.items() if (now - t) >= self.PORT_TTL_SECONDS and p not in new_port_map]
            for p in expired:
                del self._port_last_seen[p]
            # Bersihkan remote-IP fallback yang basi
            for rip in [r for r, (_a, _p, ts) in self._remote_to_proc.items() if (now - ts) >= self.REMOTE_TTL_SECONDS]:
                del self._remote_to_proc[rip]
            # Bersihkan pid cache yang sudah mati (cegah stale setelah PID reuse)
            if len(self._pid_cache) > 500:
                for cached_pid in list(self._pid_cache.keys()):
                    if cached_pid != 0 and cached_pid not in live_pids:
                        # Simpan sebagian, hapus yang sudah tidak live
                        del self._pid_cache[cached_pid]
                        if len(self._pid_cache) < 300:
                            break
            # Update online status, pids, and ports
            for app_name, app_info in self._apps.items():
                if app_name in active_apps:
                    app_info.is_online = True
                    app_info.pids = active_apps[app_name]
                    app_info.ports = active_ports.get(app_name, set())
                    self._app_last_seen[app_name] = now
                else:
                    # Jangan langsung offline-kan "system"/unmapped yang masih terima traffic
                    if app_name == self.UNMAPPED_APP:
                        continue
                    app_info.is_online = False
                    app_info.ports.clear()

        # Daftarkan SEMUA proses yang hidup (foreground maupun background) ala
        # NetLimiter — bukan cuma yang punya socket — agar list dinamis & lengkap.
        # Dijalankan di luar lock utama karena process_iter bisa ~50ms.
        try:
            live_names: Set[str] = set()
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pid = proc.info.get("pid") or 0
                    if pid == 0:
                        continue
                    pname = (proc.info.get("name") or "").lower().strip()
                    if not pname:
                        continue
                    live_names.add(pname)
                    live_pids.add(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            live_names = set()

        if live_names:
            with self._lock:
                for pname in live_names:
                    if pname not in self._apps:
                        _exe = ""
                        try:
                            _exe = self._pid_cache.get(next(
                                (p for p, (n, _e) in self._pid_cache.items() if n == pname), 0), ("", ""))[1]
                        except Exception:
                            _exe = ""
                        self._apps[pname] = ProcessInfo(name=pname, exe_path=_exe, is_online=False)
                    self._app_last_seen[pname] = now
                # Prune: buang app yang prosesnya sudah mati lama + tidak ada traffic.
                for app_name in list(self._apps.keys()):
                    if app_name in (self.UNMAPPED_APP,):
                        continue
                    if app_name in active_apps or app_name in live_names:
                        continue
                    info = self._apps[app_name]
                    if (info.dl_rate + info.ul_rate) > 1.0:
                        continue  # masih ada traffic (mis. via TTL port) -> simpan
                    last = self._app_last_seen.get(app_name, 0.0)
                    if last and (now - last) > self.APP_PRUNE_SECONDS:
                        del self._apps[app_name]
                        self._app_last_seen.pop(app_name, None)
                        self.app_histories.pop(app_name, None)

    def _update_nic_rates(self, elapsed: float) -> None:
        """Update total NIC throughput via psutil (sumber sama dengan Task Manager).

        Selalu jalan walau tanpa Admin/WinDivert, jadi TOTAL tetap realtime.
        """
        try:
            nic = psutil.net_io_counters()
        except Exception:
            return
        with self._lock:
            if self._nic_last_in is not None and self._nic_last_out is not None and elapsed > 0:
                d_in = nic.bytes_recv - self._nic_last_in
                d_out = nic.bytes_sent - self._nic_last_out
                # Sanity: counter reset / adapter restart ditandai delta negatif;
                # spike > 5 GB per tick (=80+ Gbps) = glitch, abaikan.
                if d_in < 0 or d_in > 5_000_000_000:
                    self._nic_last_in = nic.bytes_recv
                    d_in = 0
                if d_out < 0 or d_out > 5_000_000_000:
                    self._nic_last_out = nic.bytes_sent
                    d_out = 0
                self.nic_dl_rate = max(0.0, d_in / elapsed)
                self.nic_ul_rate = max(0.0, d_out / elapsed)
            self._nic_last_in = nic.bytes_recv
            self._nic_last_out = nic.bytes_sent

    def _calculate_rates(self) -> None:
        """Computes download and upload rates (bytes/second) based on bytes transferred in the elapsed window."""
        now = time.perf_counter()
        # Tick 0.5s: clamp bawah 0.1 agar burst singkat tidak ter-smoothing berlebihan
        elapsed = now - self.last_tick_time
        if elapsed <= 0:
            elapsed = self.scan_interval
        elapsed = max(0.1, min(elapsed, 5.0))
        self.last_tick_time = now

        # NIC rates dihitung di luar lock utama (psutil call bisa 1-5ms)
        self._update_nic_rates(elapsed)

        with self._lock:
            # Atomically extract and reset window accumulators
            current_in = self._window_bytes_in
            self._window_bytes_in = {}
            current_out = self._window_bytes_out
            self._window_bytes_out = {}
            g_ii, g_io = self._window_internet_in, self._window_internet_out
            g_li, g_lo = self._window_local_in, self._window_local_out
            self._window_internet_in = self._window_internet_out = 0
            self._window_local_in = self._window_local_out = 0
            self.internet_dl_rate = g_ii / elapsed
            self.internet_ul_rate = g_io / elapsed
            self.local_dl_rate = g_li / elapsed
            self.local_ul_rate = g_lo / elapsed
            self.total_internet_dl += g_ii
            self.total_internet_ul += g_io
            self.total_local_dl += g_li
            self.total_local_ul += g_lo

            total_dl_sec = 0.0
            total_ul_sec = 0.0

            # Union of known apps and apps with recent traffic
            all_target_names = set(self._apps.keys()) | set(current_in.keys()) | set(current_out.keys())

            for app_name in all_target_names:
                if app_name not in self._apps:
                    self._apps[app_name] = ProcessInfo(name=app_name)

                app_info = self._apps[app_name]
                bytes_in = current_in.get(app_name, 0)
                bytes_out = current_out.get(app_name, 0)

                dl_rate = bytes_in / elapsed
                ul_rate = bytes_out / elapsed

                app_info.dl_rate = dl_rate
                app_info.ul_rate = ul_rate
                app_info.total_dl += bytes_in
                app_info.total_ul += bytes_out

                total_dl_sec += dl_rate
                total_ul_sec += ul_rate

                # Record per-app history
                if app_name not in self.app_histories:
                    self.app_histories[app_name] = deque(maxlen=self.history_length)
                self.app_histories[app_name].append((now, dl_rate, ul_rate))

            # Record system-wide total history
            self.total_history.append((now, total_dl_sec, total_ul_sec))

            # Self-check presisi: grup vs jumlah per-app harus konsisten karena
            # berasal dari paket yang sama. Jika grup jauh lebih besar, catat
            # antrean atribusi (port churn / mapping basi) untuk diagnosis.
            group_total = (self.internet_dl_rate + self.local_dl_rate,
                           self.internet_ul_rate + self.local_ul_rate)
            if (group_total[0] > 50 * 1024 and group_total[0] > 3 * max(total_dl_sec, 1.0)) or \
               (group_total[1] > 50 * 1024 and group_total[1] > 3 * max(total_ul_sec, 1.0)):
                logger.warning(
                    "Attribution gap: group DL/UL=%.0f/%.0f B/s vs apps DL/UL=%.0f/%.0f B/s "
                    "(mapped=%d remote_fb=%d unmapped=%d, ports=%d remotes=%d)",
                    group_total[0], group_total[1], total_dl_sec, total_ul_sec,
                    self._stat_mapped, self._stat_remote_fb, self._stat_unmapped,
                    len(self._port_to_proc), len(self._remote_to_proc),
                )

    def _run_loop(self) -> None:
        """Background loop executed by the worker thread.

        Rate calc tiap scan_interval (0.5s), socket scan tiap socket_refresh_interval (1.0s).
        Dijaga try/except agar satu tick buruk tidak membunuh monitoring diam-diam.
        """
        while not self._stop_event.is_set():
            try:
                time.sleep(self.scan_interval)
                now = time.perf_counter()
                if (now - self._last_socket_refresh) >= self.socket_refresh_interval:
                    self._refresh_sockets()
                    self._last_socket_refresh = now
                self._calculate_rates()
            except Exception:
                logger.exception("NetworkTracker tick failed (thread kept alive)")

    def snapshot(self) -> Tuple[list, Tuple[float, float, float, float], Tuple[int, int, int, int]]:
        """Snapshot ATOMIK (apps + grup Internet/Local) dalam satu lock.

        Wajib dipakai UI agar rate grup dan per-app selalu dari tick yang sama
        (bukan race dua tick berbeda yang menampilkan total besar + app nol).
        Returns: (apps_list, (internet_dl, internet_ul, local_dl, local_ul),
                  (tot_internet_dl, tot_internet_ul, tot_local_dl, tot_local_ul)).
        """
        with self._lock:
            return (list(self._apps.values()),
                    (self.internet_dl_rate, self.internet_ul_rate,
                     self.local_dl_rate, self.local_ul_rate),
                    (self.total_internet_dl, self.total_internet_ul,
                     self.total_local_dl, self.total_local_ul))

    def refresh_now(self) -> None:
        """Paksa scan socket + hitung rate sekarang (tombol Refresh)."""
        now = time.perf_counter()
        self._refresh_sockets()
        self._last_socket_refresh = now
        self._calculate_rates()

    def get_all_apps(self) -> List[ProcessInfo]:
        """Returns a snapshot copy of all tracked applications."""
        with self._lock:
            return list(self._apps.values())

    def get_app(self, app_name: str) -> Optional[ProcessInfo]:
        """Returns details for a single application."""
        with self._lock:
            return self._apps.get(app_name.lower().strip())

    def get_history(self, app_name: Optional[str] = None) -> List[Tuple[float, float, float]]:
        """Returns the rate history tuples (timestamp, dl_rate, ul_rate)."""
        with self._lock:
            if app_name and app_name.lower() in self.app_histories:
                return list(self.app_histories[app_name.lower()])
            return list(self.total_history)

    def get_nic_rates(self) -> Tuple[float, float]:
        """Total NIC throughput (bytes/s) — sama sumbernya dengan Task Manager."""
        with self._lock:
            return self.nic_dl_rate, self.nic_ul_rate

    def get_total_rates(self) -> Tuple[float, float]:
        """Total per-app (WinDivert) + fallback NIC jika WinDivert belum ada data.

        Jika jumlah per-app ~0 tapi NIC ada traffic (mis. tanpa Admin), pakai NIC
        agar status bar tidak stuck 0 seperti Task Manager.
        """
        with self._lock:
            app_dl = sum(a.dl_rate for a in self._apps.values())
            app_ul = sum(a.ul_rate for a in self._apps.values())
            nic_dl, nic_ul = self.nic_dl_rate, self.nic_ul_rate
        # Jika WinDivert belum memberi data (non-admin / driver idle) tapi NIC aktif
        if app_dl < 1.0 and app_ul < 1.0 and (nic_dl > 1.0 or nic_ul > 1.0):
            return nic_dl, nic_ul
        # Jika selisih besar (>30%), traffic unmapped kemungkinan belum ke-mapping;
        # kembalikan nilai terbesar agar mendekati Task Manager
        if nic_dl > app_dl * 1.3:
            app_dl = nic_dl
        if nic_ul > app_ul * 1.3:
            app_ul = nic_ul
        return app_dl, app_ul
