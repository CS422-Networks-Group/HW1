## Setup Instructions

1. **Clone the repository**
```bash
   git clone <REPOSITORY-URL>
```

## Prerequisites

- Python 3.14.7 (pinned in `.python-version`)
- `traceroute` and `ping` (system tools; already present on macOS/Linux)

## Setup

We use a Python virtual environment so all three of us run the exact same
interpreter and package versions, regardless of machine. `traceroute`/`ping`
still run natively on your own machine (not virtualized), since the whole
point of this assignment is measuring *your* real network path.

```bash
make install        # creates .venv/ and installs requirements.txt into it
source .venv/bin/activate
```

Then run any script in `src/` independently, e.g.:

```bash
python src/latency_breakdown.py --input data/listed_iperf3_servers.csv
```

If you add a new dependency, install it inside the activated venv and pin
the exact version in `requirements.txt` (e.g. via `pip freeze`) so it stays
consistent for everyone else.

## 1. Ping Test and Round-Trip Time (RTT) — 50 points

2. **Create a virtual environment**
```bash
   python3 -m venv venv
```

3. **Activate the virtual environment**
```bash
   source venv/bin/activate
```

4. **Install dependencies**
```bash
   pip install -r requirements.txt
```

5. **Run the script**
```bash
   python3 src/ping_test.py <YOUR-INPUT-FILE-HERE>
```
