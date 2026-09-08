"""
Latency breakdown (HW1, Q2 a-c).

Picks 5 random destinations from the iperf3 server list, runs traceroute
against each, and records the round-trip time to every intermediate hop
along the path. Non-responsive hops (no RTT samples at all) are filtered
out of the results (2a). Then plots a stacked bar chart of the per-hop
latency breakdown for each destination (2b), and a scatter plot of hop
count vs. RTT (2c).

Usage:
    python3 src/latency_breakdown.py
"""

import argparse
import csv
import json
import os
import random
import re
import shutil
import socket
import subprocess
from pathlib import Path

import pandas as pd

from visualize import plot_hopcount_vs_rtt, plot_latency_breakdown

# Regex for validating IPv4 addresses (used in traceroute output parsing).
IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")

# Repo root (parent of src/), independent of the current working directory,
# so defaults below land in the same place whether you run this from the
# repo root, from inside src/, or with a full path.
REPO_ROOT = Path(__file__).resolve().parent.parent


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

        hop_ip = None
        latencies = []
        for i, tok in enumerate(tokens[1:], start=1):
            if tok == "ms":
                try:
                    latencies.append(float(tokens[i - 1]))
                except ValueError:
                    pass
            elif re.fullmatch(r"[\d.]+ms", tok):  # tolerate "4.543ms" too
                latencies.append(float(tok[:-2]))
            elif hop_ip is None and IP_RE.match(tok):
                hop_ip = tok

        if not latencies:
            continue  # non-responsive hop: filtered out

        hops.append(
            {
                "hop": hop_number,
                "ip": hop_ip,
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
) -> dict | None:
    """
    Use traceroute to get the latency breakdown for a given IP address or hostname.
    Finds the round-trip time from this machine to each intermediate hop along
    the path towards the destination, filtering out non-responsive hops.

    Returns {"resolved_ip": ..., "hops": [...]}, or None if the host couldn't
    be resolved or traceroute failed outright.
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
    return {"resolved_ip": resolved_ip, "hops": hops}


def to_dataframe(results: dict) -> pd.DataFrame:
    """
    Flatten the {host: {resolved_ip, hops: [...]}} results into the shape
    visualize.py's plotting functions expect: one row per responsive hop,
    with columns DEST_IP, HOP_NUM, HOP_IP, HOP_RTT.

    HOP_RTT is this hop's *latency contribution*: its RTT minus the RTT of
    the previous responsive hop (0 for the first one), per the class Q&A on
    2b. That difference is occasionally negative -- traceroute probes are
    independent, so RTT can fluctuate hop-to-hop (path changes, MPLS
    tunnels) even though real link latency can't be negative. Per the
    instructor's follow-up, that's treated as an exception and clamped to 0
    for the plotted segment, though the *next* hop's delta is still computed
    against this hop's real (unclamped) RTT, so later contributions aren't
    thrown off by the clamp. When hops in between were non-responsive
    (filtered out already), the delta lands entirely on the next responsive
    hop, i.e. it's the combined contribution of every skipped hop since the
    last response.
    """
    rows = []
    for host, data in results.items():
        if not data or not data.get("hops"):
            print(f"[{host}] no responsive hops recorded, excluding from plots")
            continue
        dest_ip = data["resolved_ip"]
        prev_rtt = 0.0
        for hop in sorted(data["hops"], key=lambda h: h["hop"]):
            rows.append(
                {
                    "DEST_IP": dest_ip,
                    "HOP_NUM": hop["hop"],
                    "HOP_IP": hop["ip"],
                    "HOP_RTT": max(0.0, hop["avg_rtt_ms"] - prev_rtt),
                }
            )
            prev_rtt = hop["avg_rtt_ms"]
    return pd.DataFrame(rows, columns=["DEST_IP", "HOP_NUM", "HOP_IP", "HOP_RTT"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", default=str(REPO_ROOT / "data" / "listed_iperf3_servers.csv"),
        help="CSV file with the iperf3 server list (columns: IP/HOST, PORT, ...).",
    )
    parser.add_argument("--count", type=int, default=5, help="Number of random targets to sample.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed, for reproducible runs.")
    parser.add_argument(
        "--output", default=str(REPO_ROOT / "latency_breakdown_results.json"),
        help="Where to write results as JSON.",
    )
    parser.add_argument(
        "--plots-dir", default=str(REPO_ROOT / "plots"),
        help="Directory to write the PDF plots into.",
    )
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
        breakdown = get_latency_breakdown(host, port, args.max_hops, args.queries, args.wait)
        results[host] = {"port": port, **(breakdown or {"resolved_ip": None, "hops": None})}

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Wrote results to {args.output}")

    df = to_dataframe(results)
    if df.empty:
        print("No responsive hops recorded for any target; skipping plots.")
        return

    os.makedirs(args.plots_dir, exist_ok=True)
    breakdown_path = os.path.join(args.plots_dir, "latency_breakdown.pdf")
    hopcount_path = os.path.join(args.plots_dir, "hopcount_vs_rtt.pdf")
    plot_latency_breakdown(df, breakdown_path)
    plot_hopcount_vs_rtt(df, hopcount_path)
    print(f"Wrote {breakdown_path} and {hopcount_path}")


if __name__ == "__main__":
    main()
