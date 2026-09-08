import argparse
import math
import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import requests
import socket
import ipaddress
import subprocess
import IP2Location
import os
import re
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from requests import get
from geopy.distance import geodesic

from visualize import get_own_location, plot_distance_vs_rtt

#matches the linux ping summary line, e.g. "rtt min/avg/max/mdev = 12.345/23.456/34.567/5.678 ms"
RTT_SUMMARY_RE = re.compile(
    r"(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = "
    r"([\d.]+)/([\d.]+)/([\d.]+)/[\d.]+ ms"
)

#check whether a value is an ip address or a host name
def is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

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
            #setting the df values
            df.loc[index, "IP/HOST"] = ip_or_host
            df.loc[index, "LATITUDE"] = response.latitude
            df.loc[index, "LONGITUDE"] = response.longitude

        #for now, drop the rows whose latitude and longitutde fields are empty
    filtered_df = df[df["LATITUDE"].notna() & df["LONGITUDE"].notna()]
    ip = get('https://api.ipify.org').content.decode('utf8')
    df.loc[len(df)] = {
        "IP/HOST": ip,
        "LATITUDE": database.get_all(ip).latitude,
        "LONGITUDE": database.get_all(ip).longitude,
    }


    return filtered_df


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
        "--threads",
        type=int,
        default=5,
        help="Number of worker threads to split the ping tests across (default: 5).",
    )
    return parser.parse_args()


def main():
    '''
    basic flow: read the csv

    then populate it with geographical data (include new columns for lat and longitude)

    update the csv

    run the ping tests

    capture the data

    plot it
    '''
    args = parse_args()

    df = process_csv(args.input_csv)
    result_df = pd.DataFrame(index=range(df.shape[0]), columns=df.columns)
    result_df["IP_ADDRESS"] = None
    result_df["MIN RTT"] = None
    result_df["MAX RTT"] = None
    result_df["AVERAGE RTT"] = None
    result_df["DISTANCE"] = None

    for index, row in df.iterrows():
        result_df.loc[index,"IP_ADDRESS"] = row["IP/HOST"]
        home_ip = (df.iloc[-1]["LATITUDE"], df.iloc[-1]["LONGITUDE"])
        dest_ip = (row["LATITUDE"], row["LONGITUDE"])
        result_df.loc[index,"DISTANCE"] = geodesic(home_ip, dest_ip).miles

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


if __name__ == "__main__":
    main()
