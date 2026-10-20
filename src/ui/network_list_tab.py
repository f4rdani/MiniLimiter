"""Network List tab — adapters, IPs and link state at a glance."""

import socket
from tkinter import ttk
from typing import Callable, Optional

import customtkinter as ctk
import psutil

from src.ui.theme import (BG_APP, BG_CARD_ALT, BG_TABLE, BORDER_COLOR,
                          FONT_FAMILY, ROW_ALT_BG, TEXT_GREEN, TEXT_MAIN,
                          TEXT_MUTED, TEXT_SUBTLE, bind_mousewheel, fit_text,
                          style_table, tree_col_width)


class NetworkListTab(ctk.CTkFrame):
    """Adapter rows: name + connection type, IP address and status."""

    def __init__(self, master, on_network_selected: Optional[Callable[[dict], None]] = None, **kwargs):
        super().__init__(master, fg_color=BG_TABLE, **kwargs)
        self.on_network_selected = on_network_selected
        self._adapters: list = []
        self._all_adapters: list = []
        self._iid_map: dict = {}
        self.search_query = ""
        self._build()
        self.refresh_adapters()

    def _build(self):
        from src.ui.theme import BTN_HOVER, RADIUS_LG
        bar = ctk.CTkFrame(self, fg_color=BG_APP, height=46)
        bar.pack(fill="x", padx=8, pady=(5, 5))
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="NETWORK ADAPTERS", height=26,
                     font=(FONT_FAMILY, 11, "bold"),
                     text_color=TEXT_SUBTLE).pack(side="left", padx=(2, 0))
        ctk.CTkButton(bar, text="↻  Refresh", width=96, height=32,
                      font=(FONT_FAMILY, 11), fg_color=BG_CARD_ALT,
                      border_width=1, border_color=BORDER_COLOR,
                      hover_color=BTN_HOVER, text_color=TEXT_MUTED,
                      corner_radius=6, command=self.refresh_adapters
                      ).pack(side="right", padx=(4, 2))
        self.lbl_count = ctk.CTkLabel(bar, text="", height=26,
                                      font=(FONT_FAMILY, 11), text_color=TEXT_SUBTLE)
        self.lbl_count.pack(side="right", padx=(4, 6))

        card = ctk.CTkFrame(self, fg_color=BG_TABLE, corner_radius=RADIUS_LG,
                            border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        style_table("NL.Treeview", rowheight=44, font_size=12)
        self.tree = ttk.Treeview(card, style="NL.Treeview",
                                 columns=("connection", "ip", "status"),
                                 show="tree headings", selectmode="browse", takefocus=0)
        self.tree.heading("#0", text="Adapter", anchor="w")
        self.tree.heading("connection", text="Type", anchor="w")
        self.tree.heading("ip", text="IP address", anchor="w")
        self.tree.heading("status", text="Status", anchor="e")
        self.tree.column("#0", width=240, anchor="w", stretch=True)
        self.tree.column("connection", width=96, anchor="w", stretch=False)
        self.tree.column("ip", width=150, anchor="w", stretch=False)
        self.tree.column("status", width=92, anchor="e", stretch=False)
        self.tree.pack(side="left", fill="both", expand=True, padx=(7, 0), pady=7)
        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=7)
        bind_mousewheel(self.tree)
        self.tree.tag_configure("active", foreground=TEXT_MAIN)
        self.tree.tag_configure("alt", background=ROW_ALT_BG)
        self.tree.tag_configure("child", foreground=TEXT_SUBTLE,
                                font=(FONT_FAMILY, 11))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._resize_job = None
        self.tree.bind("<Configure>", self._on_tree_resize)

    def destroy(self):
        try:
            if getattr(self, "_resize_job", None) is not None:
                self.after_cancel(self._resize_job)
                self._resize_job = None
        except Exception:
            pass
        super().destroy()

    def _refit_view(self) -> None:
        """Re-render so the cell text matches the current column widths."""
        try:
            self.render_adapters()
        except Exception:
            pass

    def _on_tree_resize(self, event):
        """Re-fit the cell text when the columns are resized or stretched."""
        if event.widget is not self.tree:
            return
        try:
            if self._resize_job is not None:
                self.after_cancel(self._resize_job)
        except Exception:
            pass
        try:
            self._resize_job = self.after(150, self.render_adapters)
        except Exception:
            self._resize_job = None

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel or not self.on_network_selected:
            return
        iid = sel[0]
        try:
            parent = self.tree.parent(iid)
            if parent:
                iid = parent
        except Exception:
            pass
        nic = self._iid_map.get(iid)
        if nic:
            self.on_network_selected(nic)

    def reset_columns(self) -> None:
        try:
            self.tree.column("#0", width=240)
            self.tree.column("connection", width=96)
            self.tree.column("ip", width=150)
            self.tree.column("status", width=92)
        except Exception:
            pass

    def set_search(self, query: str) -> None:
        q = (query or "").strip().lower()
        if q == self.search_query:
            return
        self.search_query = q
        self.render_adapters()

    def refresh_adapters(self):
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
        except Exception:
            return
        adapters = []
        names = sorted(
            addrs.keys(),
            key=lambda n: (0 if ("wi-fi" in n.lower() or "ethernet" in n.lower()
                                 or "wlan" in n.lower()) else 1, n))
        idx = 0
        for nic in names:
            addr_list = addrs.get(nic, [])
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
            conn = "Wi-Fi" if ("wi" in nic.lower() or "wlan" in nic.lower()) else (
                "Ethernet" if "eth" in nic.lower() else nic)
            adapters.append({
                "id": idx, "name": nic, "connection": conn,
                "ip4": ip4 or "—", "ip6": ip6 or "—", "mac": mac or "—",
                "is_up": is_up, "speed": (stat.speed if stat else 0),
                "ssid": "", "bssid": "", "gateway": "",
            })
            idx += 1
        self._all_adapters = adapters
        self._fill_wifi_and_gateway()
        self.render_adapters()

    def _fill_wifi_and_gateway(self) -> None:
        """Fill SSID/BSSID via netsh and the default gateway via ipconfig."""
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
            if ssid and self._all_adapters:
                target = next((a for a in self._all_adapters
                               if a["is_up"] and a["connection"] == "Wi-Fi"),
                              self._all_adapters[0])
                target["ssid"] = ssid
                target["bssid"] = bssid
        except Exception:
            pass
        try:
            import subprocess
            out = subprocess.check_output("ipconfig", text=True, errors="ignore", timeout=5)
            gw = ""
            for line in out.splitlines():
                if "Gateway" in line and "." in line:
                    gw = line.split(":")[-1].strip()
                    if gw:
                        break
            if gw and self._all_adapters:
                self._all_adapters[0]["gateway"] = gw
        except Exception:
            pass

    @staticmethod
    def _conn_type(adapter: dict) -> str:
        name = (adapter.get("name") or "").lower()
        conn = adapter.get("connection") or "—"
        if "wi-fi" in name or "wlan" in name:
            return "Wi-Fi"
        if "bluetooth" in name:
            return "Bluetooth"
        if "ethernet" in name:
            return "Ethernet"
        if any(k in name for k in ("warp", "local area", "vpn", "virtual", "tap")):
            return "Virtual"
        return conn

    def _col_width(self, col: str, default: int) -> int:
        """Current pixel width of a column (it stretches with the window)."""
        return tree_col_width(self.tree, col, default)

    def render_adapters(self) -> None:
        """Draw the (optionally filtered) adapter list."""
        q = self.search_query
        adapters = [
            a for a in self._all_adapters
            if not q or q in a["name"].lower() or q in a["connection"].lower()
            or q in (a.get("ip4") or "").lower() or q in (a.get("ssid") or "").lower()
        ]
        self._adapters = adapters
        self._iid_map = {}
        self.tree.delete(*self.tree.get_children())
        up = 0
        for i, a in enumerate(adapters):
            if a["is_up"]:
                up += 1
            tags = []
            if i % 2 == 1:
                tags.append("alt")
            tags.append("active" if a["is_up"] else "offline")
            label = fit_text(f"{a['id']}   {a['name']}",
                             self._col_width("#0", 240), reserve=14)
            parent = self.tree.insert(
                "", "end", text=label, open=False,
                values=(self._conn_type(a), a["ip4"],
                        "● Active" if a["is_up"] else "○ Down"),
                tags=tuple(tags))
            self._iid_map[parent] = a
            self.tree.insert(parent, "end",
                             text=f"        MAC {a['mac']}   ·   IPv6 {a['ip6']}",
                             values=("", "", ""), tags=("child",))
        try:
            self.lbl_count.configure(text=f"{len(adapters)} adapters · {up} active")
        except Exception:
            pass
