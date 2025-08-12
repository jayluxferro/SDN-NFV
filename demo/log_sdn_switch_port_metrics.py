#!/usr/bin/env python3
"""
SDN port metrics logger -> CSV

- Fetches all switches from /wm/core/controller/switches/json
- For each switch, fetches ports from /wm/core/switch/<switchId>/port/json
- Appends rows to CSV with timestamp, switchId, port_number, and all port metrics

Usage:
  python sdn_metrics_to_csv.py \
    --base-url http://localhost:8080 \
    --outfile sdn_ports_log.csv \
    --interval 0

If --interval > 0, the script will loop and log on that cadence (in seconds).
"""

import argparse
import csv
import datetime as dt
import os
import sys
import time
from typing import Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Expected metric fields from the port endpoint (kept in a stable order)
PORT_METRIC_FIELDS = [
    "receive_packets",
    "transmit_packets",
    "receive_bytes",
    "transmit_bytes",
    "receive_dropped",
    "transmit_dropped",
    "receive_errors",
    "transmit_errors",
    "receive_frame_errors",
    "receive_overrun_errors",
    "receive_CRC_errors",
    "collisions",
    "duration_sec",
    "duration_nsec",
]

CSV_FIELDS = ["timestamp", "switchId", "port_number"] + PORT_METRIC_FIELDS

def make_http_session(timeout: int = 5) -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.request_timeout = timeout
    return s

def get_switch_ids(session: requests.Session, base_url: str) -> List[str]:
    url = f"{base_url.rstrip('/')}/wm/core/controller/switches/json"
    r = session.get(url, timeout=session.request_timeout)
    r.raise_for_status()
    data = r.json()
    return [item.get("switchDPID") for item in data if item.get("switchDPID")]

def get_ports_for_switch(session: requests.Session, base_url: str, switch_id: str) -> List[Dict]:
    url = f"{base_url.rstrip('/')}/wm/core/switch/{switch_id}/port/json"
    r = session.get(url, timeout=session.request_timeout)
    r.raise_for_status()
    data = r.json()
    # Structure per sample: {"port_reply":[{"version":"OF_13","port":[{...}, ...]}]}
    replies = data.get("port_reply", [])
    if not replies:
        return []
    # Some controllers may return multiple replies; merge all ports
    ports = []
    for rep in replies:
        ports.extend(rep.get("port", []) or [])
    return ports

def ensure_csv_header(outfile: str):
    exists = os.path.isfile(outfile)
    if not exists:
        with open(outfile, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

def cast_or_default(value: str) -> str:
    """
    Keep values as strings in the CSV (as in the API),
    but gracefully handle None or other types.
    """
    if value is None:
        return ""
    return str(value)

def build_rows(switch_id: str, ports: List[Dict]) -> List[Dict[str, str]]:
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()
    rows: List[Dict[str, str]] = []
    for p in ports:
        row: Dict[str, str] = {
            "timestamp": now,
            "switchId": switch_id,
            "port_number": cast_or_default(p.get("port_number")),
        }
        for k in PORT_METRIC_FIELDS:
            row[k] = cast_or_default(p.get(k))
        rows.append(row)
    return rows

def append_rows(outfile: str, rows: List[Dict[str, str]]):
    if not rows:
        return
    with open(outfile, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerows(rows)

def snapshot_once(session: requests.Session, base_url: str, outfile: str):
    try:
        switch_ids = get_switch_ids(session, base_url)
    except Exception as e:
        print(f"[ERROR] Failed to fetch switches: {e}", file=sys.stderr)
        return

    if not switch_ids:
        print("[WARN] No switches returned by controller.", file=sys.stderr)
        return

    all_rows: List[Dict[str, str]] = []
    for sid in switch_ids:
        try:
            ports = get_ports_for_switch(session, base_url, sid)
        except Exception as e:
            print(f"[ERROR] Failed to fetch ports for {sid}: {e}", file=sys.stderr)
            continue
        rows = build_rows(sid, ports)
        all_rows.extend(rows)

    append_rows(outfile, all_rows)
    print(f"[OK] Logged {len(all_rows)} rows to {outfile}")

def main():
    parser = argparse.ArgumentParser(description="Log SDN switch port metrics to CSV.")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Controller base URL")
    parser.add_argument("--outfile", default="sdn_ports_log.csv", help="CSV output file")
    parser.add_argument("--interval", type=float, default=0.0, help="Seconds between polls; 0 = run once")
    parser.add_argument("--timeout", type=int, default=5, help="HTTP request timeout in seconds")
    args = parser.parse_args()

    ensure_csv_header(args.outfile)
    session = make_http_session(timeout=args.timeout)

    if args.interval and args.interval > 0:
        try:
            while True:
                snapshot_once(session, args.base_url, args.outfile)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[INFO] Stopped by user.")
    else:
        snapshot_once(session, args.base_url, args.outfile)

if __name__ == "__main__":
    main()
