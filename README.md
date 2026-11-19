# MiniLimiter

<p align="center">
  <img src="logo%20netlimiter.png" alt="MiniLimiter logo" width="180">
</p>

MiniLimiter is a free, lightweight, per-application internet speed limiter (*traffic shaper & bandwidth limiter*) for Windows, with a NetLimiter-inspired layout (dark mode, 2-panel split, Info View, live traffic chart).

🌐 **Website:** [f4rdani.github.io/MiniLimiter](https://f4rdani.github.io/MiniLimiter/)

---

## Features

- **Real-Time Traffic Monitor**: live list of applications using the network with Download (`DL Rate`) and Upload (`UL Rate`) speeds.
- **Bandwidth Limits (Download & Upload)**: per-application speed caps (e.g. cap `chrome.exe` at exactly `2 MB/s`).
- **Device-Level Limit**: click the `- YOUR-PC` row to cap the whole computer (e.g. `4 MB/s` for everything — verified with web speed tests).
- **Info View & Inline Rules Form**: click any application to see details and set Limit or Blocker (In/Out) with quick presets (`512 KB/s`, `1 MB/s`, `2 MB/s`, `5 MB/s`).
- **Real-Time Traffic Chart**: download (green) and upload (red/orange) curves with a live limit ceiling line.
- **Rules (Limit + Blocker)**: satu daftar semua aturan aktif dengan filter `All | Limit | Blocker`; review, enable/disable, atau delete limit/block yang dibuat.
- **Blocker**: putus koneksi per-aplikasi (drop paket via WinDivert, perlu Admin + `Blocker On`); butuh `Limiter On`? Tidak — blocker jalan sendiri meski Limiter Off.
- **Application List**: every running process (foreground and background), click to inspect.
- **Network List**: active adapters (Wi-Fi, Ethernet, IP address, SSID, gateway, connection state).
- **Sortable, resizable tables**: click any column header to sort; drag splitters and column borders; `Reset view` restores the default layout.
- **Auto UAC Elevation**: automatically requests Windows Administrator rights to load the traffic-shaping driver.
- **Single-Instance Guard**: opening the app twice only focuses the existing window — no duplicate engine, rules or tray icons.

---

## System Requirements

- Windows 10 or Windows 11 (64-bit)
- No Python required for the portable build (Python 3.10+ only for development)
- Administrator rights (required to load the *WinDivert* driver)

---

## Getting Started

### Portable release (recommended)

1. Download `MiniLimiter-vX.Y.Z-portable.zip` from the GitHub **Releases** page.
2. Extract it anywhere (e.g. `C:\Tools\MiniLimiter`).
3. Double-click **`MiniLimiter.exe`** — no `.bat` needed. Windows asks for Administrator rights (UAC); accept to enable traffic shaping.
4. If UAC is declined, the app still opens in monitoring mode.

All state (`config/rules.json`, `MiniLimiter.log`) is written **beside the EXE**, so the folder can be moved/copied to another PC without losing rules.

Building your own release:

```powershell
pip install -r requirements.txt -r requirements-build.txt
python build_portable.py --version v1.0.0
# output: dist/MiniLimiter-v1.0.0-portable.zip
```

Pushing a `v*` tag (e.g. `v1.0.0`) builds and publishes the ZIP automatically via `.github/workflows/release.yml`.

### Run from source (development)

```powershell
git clone https://github.com/f4rdani/MiniLimiter.git
cd MiniLimiter
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python src\main.py
```

`run_app.bat` remains as a development-only launcher that auto-requests admin.
Alternatively, open a terminal **as Administrator** and run `.\venv\Scripts\python src\main.py`.

Without Administrator rights the app still runs in monitoring mode (per-app speeds unavailable, totals come from the network adapter counters).

---

## Limiting Chrome downloads to 2 MB/s

1. Open the app by double-clicking `MiniLimiter.exe` (portable) or `run_app.bat` (development).
2. In the **Activity** tab, click `Google Chrome` (or `chrome.exe`).
3. In the right-hand **Info View** panel:
   - Under **Limit**, check the box in the **In (Download)** column.
   - Type `2 MB/s` (or click the `2 MB/s` preset).
   - Click **Apply Rule**.
4. Chrome downloads are capped at 2 MB/s, and the **Traffic Chart** shows a flat ceiling line at exactly 2 MB/s.

To cap the whole PC instead, click the top `- YOUR-PC` row and set the device limit there.

---

## Project Layout

```
MiniLimiter/
├── bin/                       # WinDivert driver (WinDivert.dll, WinDivert64.sys)
├── config/                    # Saved rules (rules.json, created on first run)
├── src/
│   ├── main.py                # Application entry point
│   ├── core/                  # Network engine
│   │   ├── divert_bindings.py # WinDivert ctypes bindings & fast packet parser
│   │   ├── models.py          # Rule & ProcessInfo dataclasses
│   │   ├── rules_manager.py   # Rule storage (per-app + device-level)
│   │   ├── shaper.py          # Single-handle measure-and-shape engine
│   │   ├── token_bucket.py    # Token bucket rate limiter
│   │   └── tracker.py         # Port-to-PID mapping & speed calculator
│   ├── ui/                    # Interface (NetLimiter style)
│   │   ├── activity_tab.py    # Live process tree & speed table
│   │   ├── info_view.py       # Top-right panel: details & rule editor
│   │   ├── main_window.py     # Main window (toolbar, tabs, layout, status bar)
│   │   ├── network_list_tab.py# Network adapter list
│   │   ├── rule_list_tab.py   # Rules table (Limit+Blocker + filter All/Limit/Blocker)
│   │   ├── blocker_tab.py     # Deprecated shim -> RuleListTab (backward-compat)
│   │   ├── application_list_tab.py # All running processes
│   │   ├── theme.py           # Dark theme + shared widget styling
│   │   └── traffic_chart.py   # Real-time canvas chart
│   └── utils/
│       ├── appinfo.py         # EXE version info & computer name helpers
│       ├── elevation.py       # Windows UAC admin helper (frozen-aware)
│       ├── formatters.py      # Unit formatting (autoByte, KB/s, MB/s, Mbps)
│       └── paths.py           # Portable resource/state path helpers
├── tests/                     # Unit + UI smoke tests
├── .github/workflows/release.yml # Build + publish ZIP on v* tags
├── build_portable.py          # PyInstaller onedir build + ZIP
├── requirements-build.txt     # Build-only dependencies (PyInstaller)
├── logo netlimiter.png        # App logo (window, toolbar, tray, EXE icon)
├── MiniLimiter.ico            # Generated from the PNG for the EXE/window
├── run_app.bat                # Development-only launcher with Admin UAC
└── README.md
```

---

## Measuring Accuracy

Per-application speeds are measured at the single point where packets are also shaped (exactly-once counting), so the enforced limit is what you observe — e.g. set `4 MB/s` and a web speed test peaks at ~`4 MB/s`. Absolute parity with NetLimiter (~1–3% difference from packet headers/retransmits) is expected since they measure at different network layers.

---

## License

Free for personal and commercial use. WinDivert binaries in `bin/` keep their original LGPL/GPL license.
