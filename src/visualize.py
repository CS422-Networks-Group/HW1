import math
import os

import IP2Location
import matplotlib.pyplot as plt
import pandas as pd
import requests


EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    #great-circle distance between two lat/long points, in km
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def get_own_location(db_path: str = os.path.join("data", "IP2LOCATION-LITE-DB5.BIN")) -> tuple[float, float]:
    #looks up this machine's public IP and geolocates it, for use as the distance origin
    own_ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
    database = IP2Location.IP2Location(db_path)
    response = database.get_all(own_ip)
    return response.latitude, response.longitude


def plot_distance_vs_rtt(df: pd.DataFrame, origin: tuple[float, float], output_path: str) -> None:
    '''
    scatter plot of distance vs RTT (README 1b), one point per destination IP.
    plots the average RTT with a vertical bar spanning min-max RTT, to also
    surface what the README asks about in 1c (spread between min/max and distance).
    '''
    origin_lat, origin_lon = float(origin[0]), float(origin[1])
    df = df.dropna(subset=["LATITUDE", "LONGITUDE", "MIN_RTT", "AVG_RTT", "MAX_RTT"])

    distances = [
        haversine_distance(origin_lat, origin_lon, float(lat), float(lon))
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
    '''
    stacked bar chart of per-hop latency contribution for each destination IP (README 2b).
    expects one row per responsive hop: DEST_IP, HOP_NUM, HOP_IP, HOP_RTT
    '''
    fig, ax = plt.subplots(figsize=(10, 6))

    dest_ips = df["DEST_IP"].unique()
    bottoms = {dest_ip: 0.0 for dest_ip in dest_ips}
    max_hops = df.groupby("DEST_IP")["HOP_NUM"].count().max()

    for hop_num in range(1, max_hops + 1):
        hop_rows = df[df["HOP_NUM"] == hop_num].set_index("DEST_IP")["HOP_RTT"]
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
    scatter plot of hop count vs total RTT to destination, one point per destination IP (README 2c).
    expects the same shape as plot_latency_breakdown.
    '''
    grouped = df.groupby("DEST_IP").agg(hop_count=("HOP_NUM", "count"), total_rtt=("HOP_RTT", "sum"))

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(grouped["hop_count"], grouped["total_rtt"])
    ax.set_xlabel("Hop count")
    ax.set_ylabel("Round-trip time (ms)")
    ax.set_title("Hop count vs. RTT")

    fig.savefig(output_path)
    plt.close(fig)
