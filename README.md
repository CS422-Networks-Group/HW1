# Assignment 1: Network Latencies, Ping & Traceroute

**CS 422: Computer Networks, Fall 2026**
Instructor: Vamsi Addanki
TAs: Youngsuk Kim, Xiao Luo, Albert Vo
**Due:** Tuesday, September 08, 2026 @ 23:45 ET

## Prerequisites

- Python 3.14.7 (pinned in `.python-version`)
- `traceroute` and `ping` (system tools; already present on macOS/Linux)

## Setup

We use a Python virtual environment so all three of us run the exact same
interpreter and package versions, regardless of machine. `traceroute`/`ping`
still run natively on your own machine (not virtualized), since the whole
point of this assignment is measuring *your* real network path.

1. **Clone the repository**
   ```bash
   git clone <REPOSITORY-URL>
   ```

2. **Create and install the virtual environment** (creates `.venv/`, installs
   `requirements.txt` into it, using the Python version pinned in
   `.python-version`)
   ```bash
   make install
   source .venv/bin/activate
   ```

3. **Run a script**, e.g.:
   ```bash
   python src/main.py <YOUR-INPUT-FILE-HERE>
   python src/latency_breakdown.py --input data/listed_iperf3_servers.csv
   ```

If you add a new dependency, install it inside the activated venv and pin
the exact version in `requirements.txt` (e.g. via `pip freeze`) so it stays
consistent for everyone else.

## 1. Ping Test and Round-Trip Time (RTT) — 50 points

(a) For each IP address listed at https://iperf3serverlist.net/, including your own IP address:
- Run a ping test and find the min, max, and average round-trip time (RTT).
- Find the geolocation coordinates from publicly available data.

(b) Do a scatter plot: distance vs. RTT, where distance is the geographical distance between your location and the destination IP address location. Each data point corresponds to a destination IP address.

(c) Explain whether and how distance relates to RTT. What do min and max RTT convey about the distance, and the network state?

## 2. Latency Breakdown — 50 points

(a) Pick 5 random IP addresses from the list at https://iperf3serverlist.net/. Find the round-trip time from your machine to each intermediate hop along the path towards the destination IPs using traceroute. Your script should filter out non-responsive hops.

(b) Plot a stacked bar chart showing the breakdown of latencies to each hop, corresponding to each of the five chosen destination IPs.

(c) Do a scatter plot: hop count vs. RTT. Each data point corresponds to a destination IP address.

(d) Explain your observations from these plots. How does hop count relate to RTT?

**Note:** It's fine to skip non-responsive servers (your script should handle it). You may see `*` in traceroute output, meaning the hop isn't responding to ICMP — that's fine as long as the traceroute completes with the final destination responding. Otherwise, traceroute will time out and the script should mark it non-responsive.

**Troubleshooting:** `latency_breakdown.py` uses UDP probes (traceroute's default), which some campus/university networks filter. If a trace never leaves private address space (`10.x`, `172.16-31.x`, `192.168.x`) or times out on every hop, try `sudo traceroute -I <host>` (ICMP probes) by hand to check whether that's the cause — if ICMP gets through and UDP doesn't, that's itself worth mentioning in the report.

## Report

- Include a GitHub/GitLab link in the report, with links or line ranges to the relevant code sections (e.g., a specific function or class).
- Include the plots in the report, and point to the code sections that generate them.
- All experiments should be fully automated via a script (Python, Bash, etc.) that handles corner cases like non-responsive servers.
- Script input: a file containing the list of IP addresses to ping and traceroute, plus any other command line arguments needed.
- The script should also invoke plotting and generate PDF plots all at once.
- The codebase should include all inputs and scripts needed to re-run the experiments and regenerate plots in one shot.

**Note:** Grading is based on an oral exam during PSO/office hours the week of September 14. Grace period: 72 hours. After that, 25% off per 24 hours late, rounded up.
