"""Data models for MiniLimiter."""

from dataclasses import dataclass, field
from typing import Optional, Set, Dict, Any


@dataclass
class Rule:
    """Network rule definition for an application."""
    app_name: str                         # e.g. "chrome.exe" (case-insensitive)
    limit_in: Optional[int] = None         # Download limit in bytes/sec (None = Unlimited)
    limit_out: Optional[int] = None        # Upload limit in bytes/sec (None = Unlimited)
    block_in: bool = False                 # Block all incoming traffic
    block_out: bool = False                # Block all outgoing traffic
    enabled: bool = True                   # Master rule toggle

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_name": self.app_name,
            "limit_in": self.limit_in,
            "limit_out": self.limit_out,
            "block_in": self.block_in,
            "block_out": self.block_out,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Rule":
        return cls(
            app_name=data.get("app_name", "").lower(),
            limit_in=data.get("limit_in"),
            limit_out=data.get("limit_out"),
            block_in=data.get("block_in", False),
            block_out=data.get("block_out", False),
            enabled=data.get("enabled", True),
        )


@dataclass
class ProcessInfo:
    """Represents an application tracked in the system."""
    name: str                              # Executable name, e.g. "chrome.exe"
    exe_path: str = ""                     # Full path to .exe
    pids: Set[int] = field(default_factory=set) # Set of all PIDs belonging to this app
    ports: Set[int] = field(default_factory=set) # Active local ports used
    dl_rate: float = 0.0                   # Current download rate (bytes/s)
    ul_rate: float = 0.0                   # Current upload rate (bytes/s)
    total_dl: int = 0                      # Total downloaded bytes since launch
    total_ul: int = 0                      # Total uploaded bytes since launch
    is_online: bool = False                # True if currently has active sockets
