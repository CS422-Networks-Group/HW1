import ipaddress
import shutil
import subprocess


def get_latency_breakdown(ip: str):
    """
    Using traceroute to get the latency breakdown for a given IP address.
    If the IP address is not reachable, it will return None.
    Find the round-trip time from this machine to each intermediate hop
    along the path towards destination ip addresses using traceroute. Filter
    out non-responsive hops.
    """
    # Validate that ip is actually an IP address (not a hostname, flag, or
    # shell metacharacters) before it ever reaches a subprocess call.
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise ValueError(f"Invalid IP address: {ip!r}")

    # Check if traceroute command is available
    traceroute_path = shutil.which("traceroute")
    if not traceroute_path:
        raise EnvironmentError("traceroute command is not available on this system.")

    # Run the traceroute command
    try:
        result = subprocess.run(
            [traceroute_path, ip],
            capture_output=True,
            text=True,
        )
        output = result.stdout
    except Exception as e:
        print(f"Error running traceroute: {e}")
        return None

    # Parse the output to extract latency information
    latency_breakdown = []
    for line in output.splitlines()[1:]:  # Skip the first line (header)
        parts = line.split()
        if len(parts) >= 2:
            hop_number = parts[0]
            latencies = [float(latency.replace('ms', '')) for latency in parts[1:] if 'ms' in latency]
            latency_breakdown.append((hop_number, latencies))

    return latency_breakdown
