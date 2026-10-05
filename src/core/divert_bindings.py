"""Ctypes bindings for WinDivert 2.2 with native C bitfields."""

import ctypes
import os
import struct
from pathlib import Path
from typing import Optional, Tuple

# Path to WinDivert.dll in bin/ directory
BIN_DIR = Path(__file__).resolve().parent.parent.parent / "bin"
DLL_PATH = BIN_DIR / "WinDivert.dll"

# WinDivert constants
WINDIVERT_LAYER_NETWORK = 0
WINDIVERT_FLAG_DEFAULT = 0
WINDIVERT_FLAG_SNIFF = 1
WINDIVERT_FLAG_DROP = 2

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class WINDIVERT_DATA_NETWORK(ctypes.Structure):
    _fields_ = [
        ("IfIdx", ctypes.c_uint32),
        ("SubIfIdx", ctypes.c_uint32),
    ]


class WINDIVERT_ADDRESS(ctypes.Structure):
    """WinDivert 2.2 packet address structure (80 bytes total) using native C bitfields."""
    _fields_ = [
        ("Timestamp", ctypes.c_int64),
        ("Layer", ctypes.c_uint32, 8),
        ("Event", ctypes.c_uint32, 8),
        ("Sniffed", ctypes.c_uint32, 1),
        ("Outbound", ctypes.c_uint32, 1),
        ("Loopback", ctypes.c_uint32, 1),
        ("Impostor", ctypes.c_uint32, 1),
        ("IPv6", ctypes.c_uint32, 1),
        ("IPChecksum", ctypes.c_uint32, 1),
        ("TCPChecksum", ctypes.c_uint32, 1),
        ("UDPChecksum", ctypes.c_uint32, 1),
        ("Reserved1", ctypes.c_uint32, 8),
        ("Reserved2", ctypes.c_uint32),
        ("Reserved3", ctypes.c_uint8 * 64),
    ]

    @property
    def is_outbound(self) -> bool:
        return bool(self.Outbound)

    @property
    def is_ipv6(self) -> bool:
        return bool(self.IPv6)

    @property
    def is_loopback(self) -> bool:
        return bool(self.Loopback)

    @property
    def is_impostor(self) -> bool:
        return bool(self.Impostor)


PWINDIVERT_ADDRESS = ctypes.POINTER(WINDIVERT_ADDRESS)


def load_windivert_dll() -> Optional[ctypes.CDLL]:
    """Loads the WinDivert DLL from the local bin folder."""
    if not DLL_PATH.exists():
        return None
    try:
        os.add_dll_directory(str(BIN_DIR))
    except (AttributeError, OSError):
        pass

    dll = ctypes.CDLL(str(DLL_PATH))

    # WinDivertOpen(filter, layer, priority, flags) -> HANDLE
    dll.WinDivertOpen.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int16, ctypes.c_uint64]
    dll.WinDivertOpen.restype = ctypes.c_void_p

    # URUTAN BENAR sesuai windivert.h:
    #   BOOL WinDivertRecv(HANDLE, VOID *pPacket, UINT packetLen, UINT *pRecvLen, WINDIVERT_ADDRESS *pAddr)
    #   BOOL WinDivertSend(HANDLE, const VOID *pPacket, UINT packetLen, UINT *pSendLen, const WINDIVERT_ADDRESS *pAddr)
    # Bug lama: pAddr & pRecvLen tertukar -> read_len berisi Timestamp (miliaran byte)
    # sehingga rate meledak ke puluhan GB/s. Sudah diperbaiki di sini.
    dll.WinDivertRecv.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.POINTER(ctypes.c_uint),
        PWINDIVERT_ADDRESS,
    ]
    dll.WinDivertRecv.restype = ctypes.c_bool

    dll.WinDivertSend.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.POINTER(ctypes.c_uint),
        PWINDIVERT_ADDRESS,
    ]
    dll.WinDivertSend.restype = ctypes.c_bool

    # WinDivertClose(handle) -> BOOL
    dll.WinDivertClose.argtypes = [ctypes.c_void_p]
    dll.WinDivertClose.restype = ctypes.c_bool

    # WinDivertHelperCompileFilter
    dll.WinDivertHelperCompileFilter.argtypes = [
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
        ctypes.POINTER(ctypes.c_char_p),
        ctypes.POINTER(ctypes.c_uint),
    ]
    dll.WinDivertHelperCompileFilter.restype = ctypes.c_bool

    return dll


def parse_packet_ports(raw_bytes: bytes, is_ipv6: bool) -> Optional[Tuple[int, int, int]]:
    """Fast header parser extracting (protocol, src_port, dst_port).
    
    Returns:
        (protocol, src_port, dst_port) or None if packet cannot be parsed.
        protocol: 6 for TCP, 17 for UDP.
    """
    detail = parse_packet_detail(raw_bytes, is_ipv6)
    if detail is None:
        return None
    proto, src_port, dst_port, _, _ = detail
    return proto, src_port, dst_port


def parse_packet_detail(raw_bytes: bytes, is_ipv6: bool) -> Optional[Tuple[int, int, int, str, str]]:
    """Extended parser extracting (protocol, src_port, dst_port, src_ip, dst_ip).

    IP dikembalikan sebagai string ("192.168.1.5", "93.184.216.34", "fe80::1").
    Untuk IPv6 dengan extension header, kembalikan None (dihitung sebagai Unknown).
    """
    length = len(raw_bytes)
    if not is_ipv6:
        if length < 20:
            return None
        version_ihl = raw_bytes[0]
        if (version_ihl >> 4) != 4:
            return None
        ihl = (version_ihl & 0x0F) * 4
        if length < ihl + 4:
            return None
        proto = raw_bytes[9]
        if proto not in (6, 17):
            return None
        try:
            src_port, dst_port = struct.unpack_from("!HH", raw_bytes, ihl)
            src_ip = ".".join(str(b) for b in raw_bytes[12:16])
            dst_ip = ".".join(str(b) for b in raw_bytes[16:20])
        except Exception:
            return None
        return proto, src_port, dst_port, src_ip, dst_ip
    else:
        if length < 44:
            return None
        version = raw_bytes[0] >> 4
        if version != 6:
            return None
        proto = raw_bytes[6]
        if proto not in (6, 17):
            return None
        try:
            src_port, dst_port = struct.unpack_from("!HH", raw_bytes, 40)
            import ipaddress
            src_ip = str(ipaddress.IPv6Address(raw_bytes[8:24]))
            dst_ip = str(ipaddress.IPv6Address(raw_bytes[24:40]))
        except Exception:
            return None
        return proto, src_port, dst_port, src_ip, dst_ip


def is_private_ip(ip_str: str) -> bool:
    """True untuk LocalNetwork (10/8, 172.16/12, 192.168/16, 127/8, link-local, fc00::/7, fe80::/10)."""
    try:
        import ipaddress
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved
    except Exception:
        return False
