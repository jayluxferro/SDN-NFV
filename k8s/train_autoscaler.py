#!/usr/bin/env python3
import time, json, statistics, random, argparse
from datetime import datetime, timedelta
import requests
import joblib
from collections import deque
import numpy as np
from sklearn.linear_model import LinearRegression

# A few valid GhanaPost GPS address examples from docs; adjust/add real-world ones
SAMPLE_ADDRESSES = [
    "AK-484-9321",
    "GA-184-9823",
    "AS-102-1234",
    "GS-123-4567",
    "EO-000-1111",
]


def probe_once(base_url, timeout=5):
    url = base_url.rstrip("/") + "/get-location"
    addr = random.choice(SAMPLE_ADDRESSES)
    t0 = time.perf_counter()
    try:
        r = requests.post(url, data={"address": addr}, timeout=timeout)
        latency = (time.perf_counter() - t0) * 1000.0
        ok = r.status_code == 200
        return latency, r.status_code, ok
    except Exception:
        latency = (time.perf_counter() - t0) * 1000.0
        return latency, 599, False


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--base-url",
        default="http://127.0.0.1:9091",
        help="Service base URL (e.g., http://gpgs.example.com or http://127.0.0.1:9091)",
    )
    p.add_argument(
        "--duration-secs",
        type=int,
        default=300,
        help="How long to collect data (seconds)",
    )
    p.add_argument(
        "--qps", type=float, default=5.0, help="Probing rate (requests per second)"
    )
    p.add_argument(
        "--target-p95-ms",
        type=float,
        default=400.0,
        help="Latency SLA target (p95 in milliseconds)",
    )
    p.add_argument(
        "--target-rps-per-pod",
        type=float,
        default=8.0,
        help="Heuristic baseline throughput per pod for labels",
    )
    p.add_argument(
        "--outfile", default="replica_model.pkl", help="Path to save trained model"
    )
    args = p.parse_args()

    interarrival = 1.0 / max(args.qps, 0.001)
    window = deque()
    lat_hist = []
    rows = []

    end = time.time() + args.duration_secs
    while time.time() < end:
        ts = datetime.utcnow().isoformat()
        latency, code, ok = probe_once(args.base_url)
        lat_hist.append(latency)
        now = time.time()
        window.append(now)
        # expire old timestamps for a ~5s window RPS
        while window and now - window[0] > 5.0:
            window.popleft()
        rps = len(window) / 5.0

        rows.append(
            {"ts": ts, "lat_ms": latency, "code": code, "ok": int(ok), "rps_5s": rps}
        )
        time.sleep(interarrival)

    # Features: RPS and p95 latency; Label: replicas (ceil(rps/target_rps_per_pod) adjusted by latency)
    if not rows:
        raise SystemExit("No data collected.")

    # Compute rolling p95 across entire run (you could also window this)
    p95 = statistics.quantiles([r["lat_ms"] for r in rows], n=20)[18]  # ~p95
    X = []
    y = []
    for r in rows:
        base_replicas = max(
            1, int(np.ceil(r["rps_5s"] / max(args.target_rps_per_pod, 0.1)))
        )
        # If p95 too high, nudge desired replicas upward
        lat_factor = 0
        if p95 > args.target_p95_ms:
            lat_factor = 1
        y.append(base_replicas + lat_factor)
        X.append([r["rps_5s"], p95])

    X = np.array(X)
    y = np.array(y)
    model = LinearRegression()
    model.fit(X, y)

    joblib.dump(
        {
            "model": model,
            "target_p95_ms": args.target_p95_ms,
            "default_target_rps_per_pod": args.target_rps_per_pod,
        },
        args.outfile,
    )

    # Persist raw data for inspection
    with open("training_data.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    print(f"Saved model → {args.outfile}")
    print(f"Collected {len(rows)} samples. Empirical p95 latency ≈ {p95:.1f} ms")


if __name__ == "__main__":
    main()
