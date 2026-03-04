#!/usr/bin/env python3
import csv
import os
import time
import argparse
from datetime import datetime, timezone
import requests

def fetch_state(session, base_url, sensor_base, suffix, token, timeout=3):
    """
    Get the 'state' field from e.g.
    {base_url}/api/states/{sensor_base}_{suffix}
    Returns (value_as_float_or_None, unit_str_or_None)
    """
    url = f"{base_url.rstrip('/')}/api/states/{sensor_base}_{suffix}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        r = session.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        state_str = data.get("state")
        attrs = data.get("attributes", {}) or {}
        unit = attrs.get("unit_of_measurement")
        # Home Assistant states are strings (e.g. "0.0"). Try to parse to float.
        try:
            val = float(state_str)
        except (TypeError, ValueError):
            val = None
        return val, unit
    except requests.RequestException:
        return None, None

def ensure_header(csv_path, fieldnames):
    needs_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    if needs_header:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

def main():
    parser = argparse.ArgumentParser(description="Poll current/voltage/power every second and save to CSV.")
    parser.add_argument("--base-url", default="http://10.205.10.7:8123", help="Base URL of the API (e.g. http://host:8123)")
    parser.add_argument("--token", default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJlZmZiNTIxMjBmZTY0YmZiYjM3MjdiYTEzNDRjNDA4MCIsImlhdCI6MTc1NzUxMzUzOSwiZXhwIjoyMDcyODczNTM5fQ.kektYZ6HqnNhnGkwQJwr8YjGKPsqYBVcFlski0oXBnA", help="Long-Lived Access Token (Bearer)")
    parser.add_argument("--sensor-base", default="sensor.antela_smart_plug", help="Sensor base (without _current/_voltage/_power)")
    parser.add_argument("--csv", default="readings.csv", help="Output CSV path")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds (default 1.0)")
    args = parser.parse_args()

    # Suffixes to poll; add/remove if you have more metrics
    suffixes = ["current", "voltage", "power"]

    fieldnames = ["timestamp_iso"] + [f"{s}" for s in suffixes]
    ensure_header(args.csv, fieldnames)

    session = requests.Session()

    print(f"Polling {args.base_url} for {args.sensor_base}_{{{', '.join(suffixes)}}} every {args.interval}s.")
    print(f"Writing to {args.csv}. Press Ctrl+C to stop.")
    try:
        while True:
            t_iso = datetime.now(timezone.utc).isoformat()
            row = {"timestamp_iso": t_iso}

            # Fetch each metric
            units_seen = {}
            for sfx in suffixes:
                val, unit = fetch_state(session, args.base_url, args.sensor_base, sfx, args.token)
                row[sfx] = val if val is not None else ""
                if unit:
                    units_seen[sfx] = unit

            # Append row
            with open(args.csv, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writerow(row)

            # Optional: print a tiny status line
            status = " | ".join(
                f"{sfx}: {row[sfx]}{(' ' + units_seen.get(sfx,'')) if row[sfx] != '' and units_seen.get(sfx) else ''}"
                for sfx in suffixes
            )
            print(f"{t_iso}  {status}")

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped")

if __name__ == "__main__":
    main()
