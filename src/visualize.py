import os

import IP2Location
import matplotlib.pyplot as plt
import pandas as pd
import requests
from geopy.distance import geodesic


def get_own_location(db_path: str = os.path.join("data", "IP2LOCATION-LITE-DB5.BIN")) -> tuple[float, float]:
    #looks up this machine's public IP and geolocates it, for use as the distance origin
    own_ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
    database = IP2Location.IP2Location(db_path)
    response = database.get_all(own_ip)
    return response.latitude, response.longitude


def plot_distance_vs_rtt(df: pd.DataFrame, origin: tuple[float, float], output_path: str) -> None:
    '''
    scatter plot of distance vs RTT, one point per destination IP.
    plots the average RTT with a vertical bar spanning min-max RTT.
    '''
    origin = (float(origin[0]), float(origin[1]))
    df = df.dropna(subset=["LATITUDE", "LONGITUDE", "MIN_RTT", "AVG_RTT", "MAX_RTT"])

    distances = [
        geodesic(origin, (float(lat), float(lon))).km
        for lat, lon in zip(df["LATITUDE"], df["LONGITUDE"])
    ]

    fig, ax = plt.subplots(figsize=(8, 6))
    yerr = [df["AVG_RTT"] - df["MIN_RTT"], df["MAX_RTT"] - df["AVG_RTT"]]
    ax.errorbar(distances, df["AVG_RTT"], yerr=yerr, fmt="o", ecolor="gray", elinewidth=1, capsize=2)
    ax.set_xlabel("Distance to destination (km)")
    ax.set_ylabel("Round-trip time (ms)")
    ax.set_title("Distance vs. RTT (bars show min-max range)")

    fig.savefig(output_path)
    plt.close(fig)


def plot_latency_breakdown(df: pd.DataFrame, output_path: str) -> None:
    '''Stacked bar chart of per-hop latency. Expects one row per
    responsive hop: DEST_IP, HOP_NUM, HOP_RTT (see
    main.execute_traceroute_test for how HOP_RTT is derived).'''
    fig, ax = plt.subplots(figsize=(10, 6))

    dest_ips = df["DEST_IP"].unique()
    bottoms = {dest_ip: 0.0 for dest_ip in dest_ips}
    # NB: max *hop number* seen, not count of responsive hops per destination --
    # traceroute filtering non-responsive hops leaves gaps (e.g. hops 4,5,11,12
    # responsive => count is 4 but the last hop number is 12), so counting would
    # silently truncate the higher hops off of every bar.
    max_hops = int(df["HOP_NUM"].max()) if not df.empty else 0

    for hop_num in range(1, max_hops + 1):
        hop_rows = df[df["HOP_NUM"] == hop_num].set_index("DEST_IP")["HOP_RTT"]
        if hop_rows.empty:
            continue  # no destination had a responsive hop at this number
        heights = [hop_rows.get(dest_ip, 0.0) for dest_ip in dest_ips]
        bottom = [bottoms[dest_ip] for dest_ip in dest_ips]
        ax.bar(dest_ips, heights, bottom=bottom, label=f"hop {hop_num}")
        for dest_ip, height in zip(dest_ips, heights):
            bottoms[dest_ip] += height

    ax.set_xlabel("Destination IP")
    ax.set_ylabel("Round-trip time (ms)")
    ax.set_title("Latency breakdown by hop")
    ax.legend(fontsize="small", ncol=2)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_hopcount_vs_rtt(df: pd.DataFrame, output_path: str) -> None:
    '''
    scatter plot of hop count vs total RTT to destination, one point per destination IP.
    expects the same shape as plot_latency_breakdown. total_rtt = sum of the
    (zero-clamped) HOP_RTT deltas -- see plot_latency_breakdown's docstring.
    '''
    grouped = df.groupby("DEST_IP").agg(hop_count=("HOP_NUM", "max"), total_rtt=("HOP_RTT", "sum"))

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(grouped["hop_count"], grouped["total_rtt"])
    ax.set_xlabel("Hop count")
    ax.set_ylabel("Round-trip time (ms)")
    ax.set_title("Hop count vs. RTT")

    fig.savefig(output_path)
    plt.close(fig)
