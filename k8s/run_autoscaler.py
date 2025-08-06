#!/usr/bin/env python3
import time, argparse, joblib, requests, math, statistics
from datetime import datetime
from collections import deque
from kubernetes import client, config


def current_rps(window, horizon=10.0):
    now = time.time()
    while window and now - window[0] > horizon:
        window.popleft()
    return len(window) / horizon


def probe(base_url, timeout=3.0):
    url = base_url.rstrip("/") + "/get-location"
    try:
        t0 = time.perf_counter()
        r = requests.post(url, data={"address": "AK-484-9321"}, timeout=timeout)
        lat = (time.perf_counter() - t0) * 1000.0
        return lat, r.status_code == 200
    except Exception:
        return timeout * 1000.0, False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kube-namespace", default="ghanapostgps")
    p.add_argument("--deployment", default="ghanapostgps-api")
    p.add_argument(
        "--service-url",
        default="http://ghanapostgps-api.ghanapostgps.svc.cluster.local",
    )
    p.add_argument("--model-path", default="replica_model.pkl")
    p.add_argument("--interval-secs", type=int, default=15)
    p.add_argument("--rps-window-secs", type=float, default=10.0)
    p.add_argument("--min-replicas", type=int, default=1)
    p.add_argument("--max-replicas", type=int, default=10)
    p.add_argument("--cooldown-secs", type=int, default=60)
    args = p.parse_args()

    # Kube config (in-cluster or local)
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()

    apps = client.AppsV1Api()

    bundle = joblib.load(args.model_path)
    model = bundle["model"]
    target_p95_ms = bundle.get("target_p95_ms", 400.0)

    lat_hist = deque(maxlen=200)
    ts_window = deque()
    last_scale_time = 0
    last_desired = None

    while True:
        lat, ok = probe(args.service_url)
        lat_hist.append(lat)
        ts_window.append(time.time())
        rps = current_rps(ts_window, args.rps_window_secs)
        p95 = (
            statistics.quantiles(list(lat_hist), n=20)[18]
            if len(lat_hist) >= 20
            else lat
        )

        X = [[rps, p95]]
        pred = float(model.predict(X)[0])
        desired = int(max(args.min_replicas, min(args.max_replicas, math.ceil(pred))))

        # Simple protection: if p95 << target and desired < running, allow gentle scale-down
        # else if p95 >> target, allow scale-up immediately
        now = time.time()
        can_scale = (now - last_scale_time) >= args.cooldown_secs
        if last_desired is None or (desired != last_desired and can_scale):
            # patch the deployment
            body = {"spec": {"replicas": desired}}
            apps.patch_namespaced_deployment_scale(
                name=args.deployment, namespace=args.kube_namespace, body=body
            )
            last_scale_time = now
            last_desired = desired
            print(
                f"{datetime.utcnow().isoformat()} scaled to {desired} replicas (rps={rps:.2f}, p95={p95:.1f}ms)"
            )

        time.sleep(args.interval_secs)


if __name__ == "__main__":
    main()
