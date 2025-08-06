#!/usr/bin/env python3
import asyncio, aiohttp, argparse, random, time
from statistics import mean

ADDRESSES = [
    "AK-484-9321",
    "GA-184-9823",
    "AS-102-1234",
    "GS-123-4567",
    "EO-000-1111",
    "AK4849321",
    "GA1849823",
]


async def worker(session, base_url, results, duration):
    url = base_url.rstrip("/") + "/get-location"
    end = time.time() + duration
    while time.time() < end:
        addr = random.choice(ADDRESSES)
        t0 = time.perf_counter()
        try:
            async with session.post(url, data={"address": addr}) as resp:
                await resp.read()
                lat = (time.perf_counter() - t0) * 1000.0
                results.append((lat, resp.status))
        except Exception:
            lat = (time.perf_counter() - t0) * 1000.0
            results.append((lat, 599))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base-url",
        default="http://127.0.0.1:9091",
        help="Where the service is reachable (e.g., http://gpgs.example.com)",
    )
    ap.add_argument("--concurrency", type=int, default=100)
    ap.add_argument("--duration-secs", type=int, default=120)
    args = ap.parse_args()

    results = []
    conn = aiohttp.TCPConnector(limit=args.concurrency)
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        tasks = [
            asyncio.create_task(
                worker(session, args.base_url, results, args.duration_secs)
            )
            for _ in range(args.concurrency)
        ]
        await asyncio.gather(*tasks)

    if results:
        lats = [x[0] for x in results]
        ok = sum(1 for _, s in results if 200 <= s < 300)
        rps = len(results) / args.duration_secs
        print(
            f"Sent {len(results)} reqs in {args.duration_secs}s, ~{rps:.1f} rps, "
            f"avg={mean(lats):.1f}ms, success={ok/len(results)*100:.1f}%"
        )


if __name__ == "__main__":
    asyncio.run(main())
