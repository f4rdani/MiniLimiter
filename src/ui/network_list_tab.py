"""Network List tab 1:1 NetLimiter (Screenshot 091445)."""

import socket
from tkinter import ttk
from typing import Callable, Optional
import customtkinter as ctk
import psutil

from src.ui.theme import BG_TABLE, BG_ROW_SELECTED, FONT_FAMILY, TEXT_MAIN, TEXT_MUTED, TEXT_GREEN, bind_mousewheel


class NetworkListTab(ctk.CTkFrame):
    """Rows: '0  UBSI  Wi-Fi' + driver line, 'Active' green right."""

    def __init__(self, master, on_network_selected: Optional[Callable[[dict], None]] = None, **kwargs):
        super().__init__(master, fg_color=BG_TABLE, **kwargs)
        self.on_network_selected = on_network_selected
        self._adapters: list = []
        self._build()
        self.refresh_adapters()

    def _build(self):
        from src.ui.theme import RADIUS_MD, BORDER_COLOR, style_table
        card = ctk.CTkFrame(self, fg_color=BG_TABLE, corner_radius=RADIUS_MD,
                            border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        style_table("NL.Treeview", rowheight=34, font_size=11)
        self.tree = ttk.Treeview(card, style="NL.Treeview", columns=("status",),
                                 show="tree headings", selectmode="browse", takefocus=0)
        self.tree.heading("#0", text="Adapter", anchor="w")
        self.tree.heading("status", text="Status", anchor="e")
        self.tree.column("#0", width=560, anchor="w", stretch=True)
        self.tree.column("status", width=90, anchor="e")
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 4), pady=6)
        bind_mousewheel(self.tree)
        self.tree.tag_configure("active", foreground=TEXT_GREEN)
        self.tree.tag_configure("alt", background="#232323")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel or not self.on_network_selected:
            return
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self._adapters):
            self.on_network_selected(self._adapters[idx])

    def reset_columns(self) -> None:
        try:
            self.tree.column("#0", width=560)
            self.tree.column("status", width=90)
        except Exception:
            pass

    def refresh_adapters(self):
        self.tree.delete(*self.tree.get_children())
        self._adapters = []
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
        except Exception:
            return
        # Wi-Fi / Ethernet fisik dulu, lalu sisanya
        names = sorted(addrs.keys(), key=lambda n: (0 if ("wi-fi" in n.lower() or "ethernet" in n.lower() or "wlan" in n.lower()) else 1, n))
        idx = 0
        for nic in names:
            addr_list = addrs.get(nic, [])
            # lewati loopback murni
            if nic.lower().startswith("loopback"):
                continue
            stat = stats.get(nic)
            is_up = bool(stat.isup) if stat else False
            ip4, ip6, mac = "", "", ""
            for a in addr_list:
                try:
                    if a.family == socket.AF_INET and not ip4:
                        ip4 = a.address
                    elif a.family == socket.AF_INET6 and not ip6:
                        ip6 = a.address.split("%")[0]
                    elif str(a.family) == "17" and not mac:  # AF_LINK
                        mac = a.address
                except Exception:
                    pass
            # Nama koneksi ala NetLimiter: tebak Wi-Fi vs Ethernet
            conn = "Wi-Fi" if ("wi" in nic.lower() or "wlan" in nic.lower()) else ("Ethernet" if "eth" in nic.lower() else nic)
            label = f"{idx}   {conn}   {nic}"
            status = "Active" if is_up else ""
            tags = []
            if idx % 2 == 1:
                tags.append("alt")
            if is_up:
                tags.append("active")
            parent = self.tree.insert("", "end", text="  " + label, values=(status,), tags=tuple(tags))
            # baris driver/deskripsi sebagai anak (seperti ref: Intel(R) Wi-Fi 6 ...)
            desc = nic
            self.tree.insert(parent, "end", text=f"      {desc}", values=("",))
            self._adapters.append({
                "id": idx, "name": nic, "connection": conn, "label": label,
                "ip4": ip4 or "—", "ip6": ip6 or "—", "mac": mac or "—",
                "is_up": is_up, "speed": (stat.speed if stat else 0),
                "ssid": "", "bssid": "", "gateway": "",
            })
            idx += 1
        self._fill_wifi_and_gateway()

    def _fill_wifi_and_gateway(self) -> None:
        """Isi SSID/BSSID via netsh + gateway via ipconfig (keduanya fungsional)."""
        try:
            import subprocess
            out = subprocess.check_output("netsh wlan show interfaces", text=True,
                                          errors="ignore", timeout=5)
            ssid, bssid = "", ""
            for line in out.splitlines():
                s = line.strip()
                if s.upper().startswith("SSID") and ":" in s and "BSSID" not in s.upper():
                    v = s.split(":", 1)[1].strip()
                    if v and not ssid:
                        ssid = v
                elif s.upper().startswith("BSSID"):
                    v = s.split(":", 1)[1].strip()
                    if v and not bssid:
                        bssid = v
            if ssid and self._adapters:
                # pasang ke adapter Wi-Fi yg aktif, fallback ke adapter pertama
                target = next((a for a in self._adapters
                               if a["is_up"] and a["connection"] == "Wi-Fi"), self._adapters[0])
                target["ssid"] = ssid
                target["bssid"] = bssid
        except Exception:
            pass
        # Gateway default
        try:
            import subprocess
            out = subprocess.check_output("ipconfig", text=True, errors="ignore", timeout=5)
            gw = ""
            for line in out.splitlines():
                if "Gateway" in line and "." in line:
                    gw = line.split(":")[-1].strip()
                    if gw and gw != "":
                        break
            if gw and self._adapters:
                self._adapters[0]["gateway"] = gw
        except Exception:
            pass
