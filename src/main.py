import argparse
import math
import random
import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import socket
import ipaddress
import subprocess
import IP2Location
import os
import re
from concurrent.futures import ThreadPoolExecutor
from requests import get
from geopy.distance import geodesic

from visualize import get_own_location, plot_distance_vs_rtt, plot_latency_breakdown, plot_hopcount_vs_rtt

#matches the linux ping summary line, e.g. "rtt min/avg/max/mdev = 12.345/23.456/34.567/5.678 ms"
RTT_SUMMARY_RE = re.compile(
    r"(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = "
    r"([\d.]+)/([\d.]+)/([\d.]+)/[\d.]+ ms"
)

#matches a traceroute hop line (run with -n, so no reverse-DNS names),
#e.g. " 3  192.0.2.1  12.345 ms  12.1 ms  11.9 ms"
TRACEROUTE_HOP_RE = re.compile(r"^\s*(\d+)\s+(.*)$")

#pulls each rtt probe off a hop line, e.g. "12.345 ms"
TRACEROUTE_RTT_RE = re.compile(r"([\d.]+)\s*ms")

#check whether a value is an ip address or a host name
def is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

#processing the csv for use by the functions
def process_csv(csv_file: str) -> pd.DataFrame:
    #read the csv
    df = pd.read_csv(csv_file)

    database = IP2Location.IP2Location(os.path.join("data", "IP2LOCATION-LITE-DB5.BIN"))

    #initialize two new columns
    df["LATITUDE"] = None
    df["LONGITUDE"] = None

    #read each row in csv and obtain the latitude and longitude
    for index, row in df.iterrows():
        ip_or_host = row["IP/HOST"]
        valid_ip = True
        if not is_ip_address(ip_or_host):
            try:
                ip_or_host = socket.gethostbyname(ip_or_host)
            except socket.gaierror:
                valid_ip = False
        if valid_ip:
            response = database.get_all(ip_or_host)

            # Ignore edge case for now
            if not response:
                continue

            #setting the df values
            df.loc[index, "IP/HOST"] = ip_or_host
            df.loc[index, "LATITUDE"] = response.latitude
            df.loc[index, "LONGITUDE"] = response.longitude

        #for now, drop the rows whose latitude and longitutde fields are empty
    filtered_df = df[df["LATITUDE"].notna() & df["LONGITUDE"].notna()]
    ip = get('https://api.ipify.org').content.decode('utf8')
    new_row = pd.DataFrame([{
        "IP/HOST": ip,
        "LATITUDE": database.get_all(ip).latitude,
        "LONGITUDE": database.get_all(ip).longitude,
    }])
    filtered_df = pd.concat([filtered_df, new_row], ignore_index=True)
    return filtered_df

#Part One Script Runner
def execute_ping_tests(df: pd.DataFrame, start: int, end: int):
    for index, row in df.iloc[start:end+1].iterrows():
        res = subprocess.run(
            ["ping", "-c", "11", row["IP/HOST"]],
            capture_output=True,
            text=True
        )
        print(res.stdout)

        match = RTT_SUMMARY_RE.search(res.stdout)
        if match:
            min_rtt, avg_rtt, max_rtt = (float(v) for v in match.groups())
            df.at[index, "MIN_RTT"] = min_rtt
            df.at[index, "AVG_RTT"] = avg_rtt
            df.at[index, "MAX_RTT"] = max_rtt
        else:
            df.at[index, "MIN_RTT"] = None
            df.at[index, "AVG_RTT"] = None
            df.at[index, "MAX_RTT"] = None

def execute_traceroute_test(ip_addr: str, results: list, raw_dir: str = "") -> int:
    '''
    Traceroutes ip_addr, appends one row per responsive hop (DEST_IP, HOP_NUM,
    HOP_RTT) to the shared `results` list, and returns how many negative
    hop-to-hop RTT deltas got clamped to 0 (path changes / MPLS tunnels /
    probe jitter can make a later hop's RTT sample lower than an earlier
    one, even though real link latency can't be negative).

    If raw_dir is given and a cached raw-output file for ip_addr already
    exists there (from a previous run), reuses it instead of re-running
    traceroute against the network -- with ~190 targets, re-measuring
    everyone on every run gets expensive fast. Delete the file (or the
    whole raw_dir) to force a fresh measurement for that host. A run that
    timed out isn't cached, so it's retried next time.
    '''
    raw_path = os.path.join(raw_dir, f"{ip_addr}.txt") if raw_dir else ""

    if raw_path and os.path.exists(raw_path):
        print(f"[{ip_addr}] using cached traceroute output from {raw_path}")
        with open(raw_path) as f:
            stdout = f.read()
    else:
        print(f"Run traceroute test for {ip_addr}...")
        try:
            res = subprocess.run(
                ["traceroute", "-n", "-I", ip_addr],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            print(f"[{ip_addr}] traceroute timed out, skipping")
            return 0

        stdout = res.stdout
        print(stdout)

        if raw_path and res.returncode == 0:
            # Keep the raw output on disk so re-parsing or spot-checking a hop
            # never requires re-running the measurement against the real
            # network -- and so a later run can skip this host entirely.
            os.makedirs(raw_dir, exist_ok=True)
            with open(raw_path, "w") as f:
                f.write(stdout)

    rows = []
    prev_rtt = 0.0
    clamp_count = 0
    # Don't assume the first stdout line is the "traceroute to ..." header and
    # slice it off -- on some traceroute builds that header prints to stderr,
    # not stdout, which would silently drop hop 1's real data. TRACEROUTE_HOP_RE
    # already only matches lines that start with a hop number, so no slicing
    # is needed to filter the header out.
    for line in stdout.splitlines():
        hop_match = TRACEROUTE_HOP_RE.match(line)
        if not hop_match:
            continue
        hop_num = int(hop_match.group(1))
        rest = hop_match.group(2)

        #converts each matching string to a float for processing
        rtts = [float(v) for v in TRACEROUTE_RTT_RE.findall(rest)]
        if not rtts:
            continue  # unresponsive hop ("* * *")

        raw_rtt = sum(rtts) / len(rtts)
        hop_rtt = raw_rtt - prev_rtt
        if hop_rtt < 0:
            clamp_count += 1
            hop_rtt = 0.0  # clamp decreases to 0 (edge cases above)
        prev_rtt += hop_rtt

        rows.append({
            "DEST_IP": ip_addr,
            "HOP_NUM": hop_num,
            "HOP_RTT": hop_rtt,
        })

    results.extend(rows)
    return clamp_count


def parse_args():
    parser = argparse.ArgumentParser(
        description=""
    )
    parser.add_argument(
        "input_csv",
        nargs="?",
        default="data/listed_iperf3_servers.csv",
        help="Path to a CSV file containing an IP/HOST column with the addresses to test "
             "(default: data/listed_iperf3_servers.csv).",
    )
    parser.add_argument(
        "--output-csv",
        default="data/ping_results.csv",
        help="Path to write the ping results CSV to (default: data/ping_results.csv).",
    )
    parser.add_argument(
        "--plot-output",
        default="plots/distance_vs_rtt.pdf",
        help="Path to write the distance vs. RTT plot to (default: plots/distance_vs_rtt.pdf).",
    )
    parser.add_argument(
        "--latency-breakdown-output",
        default="plots/latency_breakdown.pdf",
        help="Path to write the per-hop latency breakdown plot to (default: plots/latency_breakdown.pdf).",
    )
    parser.add_argument(
        "--hopcount-rtt-output",
        default="plots/hopcount_vs_rtt.pdf",
        help="Path to write the hop count vs. RTT plot to (default: plots/hopcount_vs_rtt.pdf).",
    )
    parser.add_argument(
        "--raw-dir",
        default="traceroute_raw",
        help="Directory to save each target's raw traceroute output into, so re-parsing or "
             "spot-checking a hop never requires re-running the measurement. Pass '' to skip "
             "saving it (default: traceroute_raw).",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=100,
        help="Number of worker threads to split the ping tests across (default: 100).",
    )

    return parser.parse_args()

def main():
    args = parse_args()

    # Process the csv file and prepare the intermediate dataframe for processing
    df = process_csv(args.input_csv)
    
    num_rows = df.shape[0]
    if num_rows:
        num_threads = max(1, min(args.threads, num_rows))
        chunk_size = math.ceil(num_rows / num_threads)
        chunk_bounds = (
            (start, min(start + chunk_size, num_rows) - 1)
            for start in range(0, num_rows, chunk_size)
        )
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(execute_ping_tests, df, start, end) for start, end in chunk_bounds]
            for future in futures:
                future.result()
    
    print(df[["IP/HOST", "MIN_RTT", "AVG_RTT", "MAX_RTT"]])
    os.makedirs(os.path.dirname(args.output_csv) or ".", exist_ok=True)
    df.to_csv(args.output_csv, index=False)

    os.makedirs(os.path.dirname(args.plot_output) or ".", exist_ok=True)
    plot_distance_vs_rtt(df, get_own_location(), args.plot_output)

    #concurrency for traceroute to prevent long execution times
    ip_addresses = df["IP/HOST"].tolist()
    traceroute_rows = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(execute_traceroute_test, ip_addr, traceroute_rows, args.raw_dir)
            for ip_addr in ip_addresses
        ]
        clamped_total = sum(future.result() for future in futures)

    if clamped_total:
        print(
            f"Clamped {clamped_total} negative hop-to-hop RTT delta(s) to 0 out of "
            f"{len(traceroute_rows)} responsive hops (path changes / MPLS tunnels / probe "
            "jitter -- see execute_traceroute_test's comments)."
        )

    traceroute_df = pd.DataFrame(traceroute_rows, columns=["DEST_IP", "HOP_NUM", "HOP_RTT"])

    # 2b wants the breakdown for 5 random destinations specifically -- sample
    # those out of the full traceroute run above rather than measuring them
    # separately, so every host only ever gets traced once. Sample only from
    # destinations that actually got responsive-hop data back.
    responsive_ips = traceroute_df["DEST_IP"].unique().tolist()
    sample_ips = random.sample(responsive_ips, k=min(5, len(responsive_ips)))
    breakdown_df = traceroute_df[traceroute_df["DEST_IP"].isin(sample_ips)]

    os.makedirs(os.path.dirname(args.latency_breakdown_output) or ".", exist_ok=True)
    plot_latency_breakdown(breakdown_df, args.latency_breakdown_output)

    # 2c wants every destination IP.
    os.makedirs(os.path.dirname(args.hopcount_rtt_output) or ".", exist_ok=True)
    plot_hopcount_vs_rtt(traceroute_df, args.hopcount_rtt_output)


if __name__ == "__main__":
    main()
