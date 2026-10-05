# MiniLimiter

MiniLimiter is a free, lightweight, per-application internet speed limiter (*traffic shaper & bandwidth limiter*) for Windows, with a NetLimiter-inspired layout (dark mode, 2-panel split, Info View, live traffic chart).

---

## Features

- **Real-Time Traffic Monitor**: live list of applications using the network with Download (`DL Rate`) and Upload (`UL Rate`) speeds.
- **Bandwidth Limits (Download & Upload)**: per-application speed caps (e.g. cap `chrome.exe` at exactly `2 MB/s`).
- **Device-Level Limit**: click the `- YOUR-PC` row to cap the whole computer (e.g. `4 MB/s` for everything — verified with web speed tests).
- **Info View & Inline Rules Form**: click any application to see details and set Limit or Blocker (In/Out) with quick presets (`512 KB/s`, `1 MB/s`, `2 MB/s`, `5 MB/s`).
- **Real-Time Traffic Chart**: download (green) and upload (red/orange) curves with a live limit ceiling line.
- **Rule List**: review, enable/disable, or delete the limits you created.
- **Blocker**: per-application block list showing every active block rule.
- **Application List**: every running process (foreground and background), click to inspect.
- **Network List**: active adapters (Wi-Fi, Ethernet, IP address, SSID, gateway, connection state).
- **Sortable, resizable tables**: click any column header to sort; drag splitters and column borders; `Reset view` restores the default layout.
- **Auto UAC Elevation**: automatically requests Windows Administrator rights to load the traffic-shaping driver.

---

## System Requirements

- Windows 10 or Windows 11 (64-bit)
- Python 3.10+
- Administrator rights (required to load the *WinDivert* driver)

---

## Getting Started

```powershell
git clone https://github.com/f4rdani/MiniLimiter.git
cd MiniLimiter
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Run (recommended)

Double-click:

```
run_app.bat
```

It requests Administrator rights (Windows UAC) and launches the app with full traffic shaping.

### Run from a terminal (PowerShell / Command Prompt)

Open a terminal **as Administrator**, then:

```powershell
cd MiniLimiter
.\venv\Scripts\python src\main.py
```

Without Administrator rights the app still runs in monitoring mode (per-app speeds unavailable, totals come from the network adapter counters).

---

## Limiting Chrome downloads to 2 MB/s

1. Open the app via `run_app.bat`.
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
│   │   ├── rule_list_tab.py   # Active rules table
│   │   ├── blocker_tab.py     # Active block rules table
│   │   ├── application_list_tab.py # All running processes
│   │   ├── theme.py           # Dark theme + shared widget styling
│   │   └── traffic_chart.py   # Real-time canvas chart
│   └── utils/
│       ├── appinfo.py         # EXE version info & computer name helpers
│       ├── elevation.py       # Windows UAC admin helper
│       └── formatters.py      # Unit formatting (autoByte, KB/s, MB/s, Mbps)
├── tests/                     # Unit + UI smoke tests
├── run_app.bat                # Launcher with Admin UAC
└── README.md
```

---

## Measuring Accuracy

Per-application speeds are measured at the single point where packets are also shaped (exactly-once counting), so the enforced limit is what you observe — e.g. set `4 MB/s` and a web speed test peaks at ~`4 MB/s`. Absolute parity with NetLimiter (~1–3% difference from packet headers/retransmits) is expected since they measure at different network layers.

---

## License

Free for personal and commercial use. WinDivert binaries in `bin/` keep their original LGPL/GPL license.
