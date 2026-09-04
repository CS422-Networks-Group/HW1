import shutil
import subprocess
import threading


def _run_traceroute(traceroute_path: str, ip: str, port: int | None):
    cmd = [traceroute_path]
    if port is not None:
        cmd += ["-p", str(port)]
    cmd.append(ip)

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout

    latency_breakdown = []
    for line in output.splitlines()[1:]:  # Skip the first line (header)
        parts = line.split()
        if len(parts) >= 2:
            hop_number = parts[0]
            latencies = [float(latency.replace('ms', '')) for latency in parts[1:] if 'ms' in latency]
            latency_breakdown.append((hop_number, latencies))

    return latency_breakdown


def get_latency_breakdown(ip: str, port: int | tuple[int, int] | None = None):
    """
    Using traceroute to get the latency breakdown for a given IP address or hostname.
    Find the round-trip time from this machine to each intermediate hop
    along the path towards destination ip addresses using traceroute. Filter
    out non-responsive hops.

    port: None for traceroute's default port, an int for a single port, or
    an (start, end) tuple to sweep an inclusive port range.
    """
    traceroute_path = shutil.which("traceroute")
    if not traceroute_path:
        raise EnvironmentError("traceroute command is not available on this system.")

    try:
        if isinstance(port, tuple):
            start, end = port
            return {p: _run_traceroute(traceroute_path, ip, p) for p in range(start, end + 1)}
        return _run_traceroute(traceroute_path, ip, port)
    except Exception as e:
        print(f"Error running traceroute: {e}")
        return None


targets = [
    ("lg.ams-nl.gigahost.no", (9201, 9240)),
    ("185.102.217.170", 5201),
    ("138.199.57.129", 5201),
    ("a204.speedtest.wobcom.de", 5201),
    ("156.146.53.53", 5201)
]

# Create a separate thread for each target to run traceroute concurrently

threads = []
for target, port in targets:
    thread = threading.Thread(target=get_latency_breakdown, args=(target, port))
    threads.append(thread)
    thread.start()

# Wait for all threads to complete
for thread in threads:
    thread.join()
