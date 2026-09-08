"""
Latency breakdown (HW1, Q2 a-c): traceroute 5 random destinations, plot the
per-hop latency breakdown (2b) and hop count vs. RTT (2c).

Usage: python3 src/latency_breakdown.py
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


def load_targets(csv_path: str) -> list[str]:
    """Load the list of hosts/IPs from the iperf3 server list CSV."""
    targets = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            host = (row.get("IP/HOST") or "").strip()
            if host:
                targets.append(host)
    return targets


def pick_random_targets(targets: list[str], count: int, seed: int | None = None) -> list[str]:
    rng = random.Random(seed)
    return rng.sample(targets, k=min(count, len(targets)))


def _parse_traceroute_output(output: str) -> list[dict]:
    """Parse `-n` traceroute stdout into responsive hops (e.g. "1  192.168.4.1
    4.543 ms"), dropping hops with zero RTT samples (e.g. "2  * *")."""
    hops = []
    for line in output.splitlines():
        tokens = line.split()
        # tokens[0].isdigit() also skips a header line, if one shows up here --
        # don't assume it's always on line 0: on this traceroute build the
        # "traceroute to ... hops max..." header prints to stderr, not stdout,
        # so slicing off "line 0" here previously discarded hop 1's real data.
        if not tokens or not tokens[0].isdigit():
            continue
        hop_number = int(tokens[0])

        hop_ip = ""  # stays empty if no IP token is found on this hop's line
        latencies = []
        for i, tok in enumerate(tokens[1:], start=1):
            if tok == "ms":
                try:
                    latencies.append(float(tokens[i - 1]))
                except ValueError:
                    pass
            elif re.fullmatch(r"[\d.]+ms", tok):  # tolerate "4.543ms" too
                latencies.append(float(tok[:-2]))
            elif not hop_ip and IP_RE.match(tok):
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
    max_hops: int,
    queries: int,
    wait: int,
    raw_path: str = "",
) -> list[dict]:
    cmd = [traceroute_path, "-n", "-m", str(max_hops), "-q", str(queries), "-w", str(wait), ip]

    timeout = max_hops * queries * wait + 30
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if raw_path:
        # Keep the raw output on disk so re-parsing or spot-checking a hop
        # never requires re-running the measurement against the real network.
        os.makedirs(os.path.dirname(raw_path), exist_ok=True)
        with open(raw_path, "w") as f:
            f.write(result.stdout)

    return _parse_traceroute_output(result.stdout)


def get_latency_breakdown(
    host: str,
    max_hops: int = 30,
    queries: int = 3,
    wait: int = 1,
    raw_dir: str = "",
) -> dict:
    """Traceroute `host`, filtering out non-responsive hops. Always returns
    {"resolved_ip": ..., "hops": [...]}; both are empty on failure."""
    try:
        resolved_ip = socket.gethostbyname(host)
    except socket.gaierror as e:
        print(f"[{host}] could not resolve host: {e}")
        return {"resolved_ip": "", "hops": []}
    print(f"[{host}] resolved to {resolved_ip}")

    traceroute_path = shutil.which("traceroute")
    if not traceroute_path:
        raise EnvironmentError("traceroute command is not available on this system.")

    raw_path = os.path.join(raw_dir, f"{resolved_ip}.txt") if raw_dir else ""
    print(f"[{resolved_ip}] running traceroute...")
    try:
        hops = _run_traceroute(traceroute_path, resolved_ip, max_hops, queries, wait, raw_path)
    except Exception as e:
        print(f"[{resolved_ip}] traceroute failed: {e}")
        return {"resolved_ip": resolved_ip, "hops": []}

    print(f"[{resolved_ip}] {len(hops)} responsive hop(s): {hops}")
    return {"resolved_ip": resolved_ip, "hops": hops}


def to_dataframe(results: dict) -> pd.DataFrame:
    """Flatten {host: {resolved_ip, hops: [...]}} into one row per responsive
    hop (DEST_IP, HOP_NUM, HOP_IP, HOP_RTT) for visualize.py's plots."""
    rows = []
    clamped = 0
    for host, data in results.items():
        if not data["hops"]:
            print(f"[{host}] no responsive hops recorded, excluding from plots")
            continue
        dest_ip = data["resolved_ip"]
        prev_rtt = 0.0
        for hop in sorted(data["hops"], key=lambda h: h["hop"]):
            # HOP_RTT = this hop's RTT minus the previous responsive hop's (per
            # class Q&A on 2b); occasionally negative from probe jitter/path
            # changes, clamped to 0 per the instructor's follow-up, though the
            # *next* delta still uses this hop's real, unclamped RTT.
            delta = hop["avg_rtt_ms"] - prev_rtt
            if delta < 0:
                clamped += 1
            rows.append(
                {
                    "DEST_IP": dest_ip,
                    "HOP_NUM": hop["hop"],
                    "HOP_IP": hop["ip"],
                    "HOP_RTT": max(0.0, delta),
                }
            )
            prev_rtt = hop["avg_rtt_ms"]

    if clamped:
        print(
            f"Clamped {clamped} negative hop-to-hop RTT delta(s) to 0 out of {len(rows)} "
            "responsive hops (path changes / MPLS tunnels / probe jitter -- see to_dataframe's comments)."
        )
    return pd.DataFrame(rows, columns=["DEST_IP", "HOP_NUM", "HOP_IP", "HOP_RTT"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", default=str(REPO_ROOT / "data" / "listed_iperf3_servers.csv"),
        help="CSV file with the iperf3 server list (must have an IP/HOST column).",
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
    parser.add_argument(
        "--raw-dir", default=str(REPO_ROOT / "traceroute_raw"),
        help="Directory to save each target's raw traceroute output into, so re-parsing "
             "never requires re-running the measurement. Pass '' to skip saving it.",
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
    for host in chosen:
        results[host] = get_latency_breakdown(host, args.max_hops, args.queries, args.wait, args.raw_dir)

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
