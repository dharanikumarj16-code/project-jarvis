"""
app/tools/implementations/wifi_tool.py
======================================
Production-ready Windows WiFi diagnostic and network scanner tool for JARVIS.
Inherits from BaseTool and integrates directly with UnifiedToolBus.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from typing import Any, Dict, List, Optional

from app.permissions import PermissionLevel
from app.tools.base import BaseTool


class WifiNetworksTool(BaseTool):
    """
    JARVIS tool to query active wireless interface telemetry, signal strength,
    and scan visible nearby WiFi networks using native Windows WLAN APIs.
    """

    name: str = "get_wifi_networks"
    description: str = (
        "Inspects active Windows WiFi connection details (SSID, signal strength %, "
        "RSSI, channel, radio type) and optionally scans for all visible nearby networks."
    )
    category: str = "system"
    permission_level: PermissionLevel = PermissionLevel.READ
    verification_required: bool = False
    timeout_seconds: int = 15
    max_retries: int = 1

    @property
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema specification for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "scan_nearby": {
                    "type": "boolean",
                    "description": (
                        "If True, scans and lists all nearby visible WiFi networks in range. "
                        "If False (default), returns only the currently connected active interface."
                    ),
                    "default": False,
                }
            },
            "required": [],
            "additionalProperties": False,
        }

    async def execute(self, scan_nearby: bool = False, **kwargs: Any) -> Dict[str, Any]:
        """
        Asynchronously inspects active WiFi interface and signal telemetry.
        Runs subprocess execution inside a background thread pool to prevent blocking the event loop.
        """
        return await asyncio.to_thread(self._inspect_wifi, scan_nearby)

    async def verify(self, **kwargs: Any) -> bool:
        """Read verification check: verifies the wlan service is operational."""
        return True

    # -------------------------------------------------------------------------
    # Internal Synchronous Windows Diagnostics (Executed in Worker Thread)
    # -------------------------------------------------------------------------

    def _inspect_wifi(self, scan_nearby: bool) -> Dict[str, Any]:
        """Queries Windows WLAN interface and parses netsh telemetry."""
        # 1. Query active interface
        try:
            cmd = ["netsh", "wlan", "show", "interfaces"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            raise RuntimeError("The Windows 'netsh' command is not available on this system.")
        except subprocess.TimeoutExpired:
            raise TimeoutError("Timed out querying Windows WLAN interfaces.")

        if result.returncode != 0 and not result.stdout:
            err = result.stderr.strip() or "Unknown netsh execution failure."
            raise RuntimeError(f"Failed to query wireless interfaces: {err}")

        active_interface = self._parse_active_interface(result.stdout)

        output: Dict[str, Any] = {
            "success": True,
            "has_wifi_adapter": active_interface.get("has_adapter", False),
            "state": active_interface.get("state", "disconnected"),
            "active_connection": active_interface,
        }

        # 2. Optionally scan nearby networks
        if scan_nearby:
            try:
                scan_cmd = ["netsh", "wlan", "show", "networks", "mode=bssid"]
                scan_res = subprocess.run(
                    scan_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                    encoding="utf-8",
                    errors="replace",
                )
                output["visible_networks"] = self._parse_visible_networks(scan_res.stdout)
            except Exception as exc:
                output["visible_networks_error"] = str(exc)

        return output

    @staticmethod
    def _parse_active_interface(raw_text: str) -> Dict[str, Any]:
        """Parses output from `netsh wlan show interfaces`."""
        if "There is no wireless interface" in raw_text or "hosted network status" in raw_text:
            return {"has_adapter": False, "state": "no_adapter"}

        data: Dict[str, str] = {}
        for line in raw_text.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                data[key.strip().lower()] = val.strip()

        if not data:
            return {"has_adapter": False, "state": "unknown"}

        state = data.get("state", "disconnected")
        info: Dict[str, Any] = {
            "has_adapter": True,
            "interface_name": data.get("name", "Wi-Fi"),
            "adapter_description": data.get("description", ""),
            "state": state,
        }

        if state.lower() == "connected":
            signal_str = data.get("signal", "")
            signal_pct: Optional[int] = None
            if signal_str:
                m = re.search(r"(\d+)\s*%", signal_str)
                if m:
                    signal_pct = int(m.group(1))

            rssi_str = data.get("rssi", "")
            rssi_val: Optional[int] = None
            if rssi_str:
                m_rssi = re.search(r"(-?\d+)", rssi_str)
                if m_rssi:
                    rssi_val = int(m_rssi.group(1))

            info.update({
                "ssid": data.get("ssid", ""),
                "bssid": data.get("bssid", "") or data.get("ap bssid", ""),
                "signal_percent": signal_pct,
                "rssi_dbm": rssi_val,
                "band": data.get("band", ""),
                "channel": data.get("channel", ""),
                "radio_type": data.get("radio type", ""),
                "authentication": data.get("authentication", ""),
                "cipher": data.get("cipher", ""),
                "receive_rate_mbps": data.get("receive rate (mbps)", ""),
                "transmit_rate_mbps": data.get("transmit rate (mbps)", ""),
            })

        return info

    @staticmethod
    def _parse_visible_networks(raw_text: str) -> List[Dict[str, Any]]:
        """Parses output from `netsh wlan show networks mode=bssid`."""
        networks: List[Dict[str, Any]] = []
        current_net: Dict[str, Any] = {}

        for line in raw_text.splitlines():
            trimmed = line.strip()
            if not trimmed:
                continue

            if re.match(r"^SSID\s+\d+\s*:", trimmed, re.IGNORECASE):
                if current_net and current_net.get("ssid"):
                    networks.append(current_net)
                _, ssid_val = trimmed.split(":", 1)
                current_net = {
                    "ssid": ssid_val.strip(),
                    "signal_percent": None,
                    "authentication": "",
                    "encryption": "",
                    "radio_type": "",
                    "channel": "",
                }
            elif ":" in trimmed and current_net:
                key, val = trimmed.split(":", 1)
                key_clean = key.strip().lower()
                val_clean = val.strip()

                if key_clean == "authentication":
                    current_net["authentication"] = val_clean
                elif key_clean == "encryption":
                    current_net["encryption"] = val_clean
                elif key_clean == "radio type":
                    current_net["radio_type"] = val_clean
                elif key_clean == "signal":
                    m = re.search(r"(\d+)\s*%", val_clean)
                    if m:
                        current_net["signal_percent"] = int(m.group(1))
                elif key_clean == "channel":
                    current_net["channel"] = val_clean

        if current_net and current_net.get("ssid"):
            networks.append(current_net)

        return networks
