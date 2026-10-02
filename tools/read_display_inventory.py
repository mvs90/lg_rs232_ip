#!/usr/bin/env python3
"""Read-only LG Signage inventory. Uses only explicitly allowlisted queries.

python3 tools/read_display_inventory.py DISPLAY_IP --output local/inventory.json
No power/input writes, remote keys, authentication or network configuration.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import socket
import time

QUERIES = {
    "power": "ka",
    "model": "fv",
    "software": "fz",
    "input": "xb",
    "temperature": "dn",
    "elapsed_hours": "dl",
    "no_signal_power_off": "fg",
    "dpm": "fj",
    "wake_on_lan": "fw",
    "power_on_status": "tr",
    "picture_mode": "dx",
    "sound_mode": "dy",
    "energy_saving": "jq",
    "backlight": "mg",
    "brightness": "kh",
    "language": "fi",
    "screen_mute": "kd",
    "fan_status": "dw",
    "failover": "mi",
    "signal": "sv 02",
    "pm_status": "sv 03",
    "temperature_sensors": "sv 07",
    "illuminance": "sv 17",
    "pm_mode": "sn 0c",
    "dpm_wakeup": "sn 0b",
    "no_signal_image": "sn a9",
}


def read_query(host, port, set_id, query, timeout=3):
    """One query per connection so a late frame cannot satisfy the next query."""
    if query not in QUERIES.values() and query != "fy":
        raise ValueError("Query is not in the read-only allowlist")
    parts = query.split()
    request = f"{parts[0]} {set_id:02x} " + " ".join(parts[1:] + ["ff"]) + "\r"
    with socket.create_connection((host, port), timeout) as conn:
        conn.settimeout(timeout)
        conn.sendall(request.encode("ascii"))
        data = b""
        deadline = time.monotonic() + timeout
        while not data.rstrip().endswith(b"x") or data.strip() == b"x":
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Incomplete acknowledgement")
            conn.settimeout(remaining)
            chunk = conn.recv(1024)
            if not chunk:
                raise ConnectionError("Connection closed before acknowledgement")
            data += chunk
            if len(data) > 4096:
                raise ValueError("Acknowledgement exceeds size limit")
    frame = data.decode("ascii").strip()
    if not re.fullmatch(
        rf"{parts[0][1]}\s+{set_id:02x}\s+(?:OK|NG)[^\r\n]*x", frame, re.I
    ):
        raise ValueError("Unexpected acknowledgement")
    return {"request": request.strip(), "response": frame}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=9761)
    parser.add_argument("--set-id", type=lambda value: int(value, 16), default=1)
    parser.add_argument(
        "--include-serial", action="store_true", help="Private output only"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.set_id <= 254:
        parser.error("Set ID must be 01..fe, never a broadcast address")
    queries = dict(QUERIES)
    if args.include_serial:
        queries["serial"] = "fy"
    results = {}
    for name, query in queries.items():
        try:
            results[name] = read_query(args.host, args.port, args.set_id, query)
        except (OSError, ValueError) as error:
            results[name] = {"error": str(error)}
        print(
            f"{name}: {'error' if 'error' in results[name] else 'recorded'}", flush=True
        )
        time.sleep(0.4)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Addresses/serial data are intentionally private; do not commit the output.
    args.output.write_text(
        json.dumps(
            {
                "host": args.host,
                "port": args.port,
                "set_id": args.set_id,
                "date": datetime.now(timezone.utc).isoformat(),
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )
    args.output.chmod(0o600)


if __name__ == "__main__":
    main()
