"""
Latency breakdown (HW1, Q2a).

Picks 5 random destinations from the iperf3 server list, runs traceroute
against each, and records the round-trip time to every intermediate hop
along the path. Non-responsive hops (no RTT samples at all) are filtered
out of the results.

Usage:
    python3 src/latency_breakdown.py \
        --input listed_iperf3_servers.csv \
        --count 5 \
        --output latency_breakdown_results.json
"""

import argparse
import csv
import json
import random
import re
import shutil
import socket
import subprocess


def parse_port(port_field: str) -> int | None:
    """Parse a PORT field from the server list CSV into a single port number.

    Fields may be blank (use traceroute's default port), a single port
    ("5201"), or an inclusive range ("9205-9240"). For a range we just use
    the first port -- traceroute only needs *a* destination port, not the
    full iperf3 service range.
    """
    port_field = (port_field or "").strip()
    if not port_field:
        return None
    first = port_field.split("-")[0].strip()
    return int(first) if first.isdigit() else None


def load_targets(csv_path: str) -> list[tuple[str, int | None]]:
    """Load (host, port) pairs from the iperf3 server list CSV."""
    targets = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            host = (row.get("IP/HOST") or "").strip()
            if not host:
                continue
            targets.append((host, parse_port(row.get("PORT", ""))))
    return targets


def pick_random_targets(
    targets: list[tuple[str, int | None]], count: int, seed: int | None = None
) -> list[tuple[str, int | None]]:
    rng = random.Random(seed)
    return rng.sample(targets, k=min(count, len(targets)))


def _parse_traceroute_output(output: str) -> list[dict]:
    """Parse traceroute output into a list of responsive hops.

    A hop line looks like (with -n, so no reverse-DNS names):
        1  192.168.4.1  4.543 ms  3.727 ms
    A hop that never replies looks like:
        2  * *
    Hops with zero RTT samples are considered non-responsive and dropped.
    """
    hops = []
    for line in output.splitlines()[1:]:  # skip the "traceroute to ..." header
        tokens = line.split()
        if not tokens or not tokens[0].isdigit():
            continue
        hop_number = int(tokens[0])

        latencies = []
        for i, tok in enumerate(tokens[1:], start=1):
            if tok == "ms":
                try:
                    latencies.append(float(tokens[i - 1]))
                except ValueError:
                    pass
            else:
                match = re.fullmatch(r"[\d.]+ms", tok)  # tolerate "4.543ms" too
                if match:
                    latencies.append(float(tok[:-2]))

        if not latencies:
            continue  # non-responsive hop: filtered out

        hops.append(
            {
                "hop": hop_number,
                "rtts_ms": latencies,
                "avg_rtt_ms": sum(latencies) / len(latencies),
            }
        )
    return hops


def _run_traceroute(
    traceroute_path: str,
    ip: str,
    port: int | None,
    max_hops: int,
    queries: int,
    wait: int,
) -> list[dict]:
    cmd = [traceroute_path, "-n", "-m", str(max_hops), "-q", str(queries), "-w", str(wait)]
    if port is not None:
        cmd += ["-p", str(port)]
    cmd.append(ip)

    timeout = max_hops * queries * wait + 30
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return _parse_traceroute_output(result.stdout)


def get_latency_breakdown(
    host: str,
    port: int | None = None,
    max_hops: int = 30,
    queries: int = 3,
    wait: int = 1,
) -> list[dict] | None:
    """
    Use traceroute to get the latency breakdown for a given IP address or hostname.
    Finds the round-trip time from this machine to each intermediate hop along
    the path towards the destination, filtering out non-responsive hops.
    """
    try:
        resolved_ip = socket.gethostbyname(host)
    except socket.gaierror as e:
        print(f"[{host}] could not resolve host: {e}")
        return None
    print(f"[{host}] resolved to {resolved_ip}")

    traceroute_path = shutil.which("traceroute")
    if not traceroute_path:
        raise EnvironmentError("traceroute command is not available on this system.")

    print(f"[{resolved_ip}] running traceroute...")
    try:
        hops = _run_traceroute(traceroute_path, resolved_ip, port, max_hops, queries, wait)
    except Exception as e:
        print(f"[{resolved_ip}] traceroute failed: {e}")
        return None

    print(f"[{resolved_ip}] {len(hops)} responsive hop(s): {hops}")
    return hops


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", default="listed_iperf3_servers.csv",
        help="CSV file with the iperf3 server list (columns: IP/HOST, PORT, ...).",
    )
    parser.add_argument("--count", type=int, default=5, help="Number of random targets to sample.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed, for reproducible runs.")
    parser.add_argument("--output", default="latency_breakdown_results.json", help="Where to write results as JSON.")
    parser.add_argument("--max-hops", type=int, default=30)
    parser.add_argument("--queries", type=int, default=3, help="Probes sent per hop.")
    parser.add_argument("--wait", type=int, default=1, help="Seconds to wait for a probe response.")
    args = parser.parse_args()

    targets = load_targets(args.input)
    if not targets:
        raise SystemExit(f"No targets found in {args.input}")

    chosen = pick_random_targets(targets, args.count, args.seed)
    print(f"Selected {len(chosen)} random target(s): {chosen}")

    results = {}
    for host, port in chosen:
        results[host] = {
            "port": port,
            "hops": get_latency_breakdown(host, port, args.max_hops, args.queries, args.wait),
        }

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Wrote results to {args.output}")


if __name__ == "__main__":
    main()
