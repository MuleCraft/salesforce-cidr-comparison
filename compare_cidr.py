from flask import Flask, request, jsonify
import requests, subprocess, os, json, ipaddress, sys

app = Flask(__name__)

STATIC_CIDRS = [
  "3.228.190.251/32",
  "34.206.116.149/32",
  "35.174.143.92/32",
  "52.203.77.201/32",
  "54.156.107.163/32",
  "54.158.77.4/32",
  "54.163.166.54/32",
  "54.83.60.38/32",
  "107.21.202.122/32",
  "3.225.151.145/32",
  "3.225.240.254/32",
  "18.204.28.162/32",
  "18.211.105.61/32",
  "34.197.58.108/32",
  "34.204.111.166/32",
  "52.3.16.30/32",
  "52.22.251.194/32",
  "52.70.135.185/32",
  "155.226.144.0/22",
  "155.226.156.0/23",
  "155.226.128.0/21",
  "3.146.43.224/28",
  "13.56.32.176/28",
  "13.58.135.64/28",
  "13.108.0.0/14",
  "34.211.108.32/28",
  "34.226.36.48/28",
  "35.182.14.32/28",
  "66.231.80.0/20",
  "68.232.192.0/20",
  "96.43.144.0/20",
  "128.17.0.0/16",
  "128.245.0.0/16",
  "136.146.0.0/15",
  "198.245.80.0/20",
  "199.122.120.0/21",
  "204.14.232.0/21"
]
def fetch_json_cidrs():
    # ... (same as before, unchanged) ...
    url = "https://ip-ranges.salesforce.com/ip-ranges.json"
    REGIONS = {"us-east-1", "us-east-2", "us-west-2"}
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        d = r.json()
        cidrs = []
        for entry in d.get("prefixes", []):
            if entry.get("provider") == "aws" and entry.get("region") in REGIONS:
                cidrs.extend(entry.get("ip_prefix", []))
        print(f"Loaded {len(cidrs)} Hyperforce AWS us-east/west CIDRs from JSON")
        return cidrs
    except Exception as e:
        print("ERROR fetching Salesforce JSON:", e)
        return []

def get_lb_cidrs(lb_name, org, client, secret):
    cmd = [
        "anypoint-cli", "cloudhub", "load-balancer", "describe", lb_name,
        "--organization", org,
        "--client_id", client,
        "--client_secret", secret,
        "--output", "json"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"Anypoint CLI ERROR for {lb_name}:\n{proc.stderr}")
        return []
    obj = json.loads(proc.stdout)
    allowlist_raw = obj.get("Allowlisted IPs", "")
    if not allowlist_raw:
        print(f"WARNING: No allowlisted IPs found for '{lb_name}'!")
        return []
    allowlist = [ip.strip() for ip in allowlist_raw.split(",") if ip.strip()]
    return allowlist

def to_networks(ip_list):
    nets = []
    for c in ip_list:
        c = c.strip()
        try:
            nets.append(ipaddress.ip_network(c, strict=False))
        except Exception:
            try:
                nets.append(ipaddress.ip_network(f"{c}/32", strict=False))
            except Exception as e:
                print("Could not parse", c, e)
    return nets

def is_covered(req, allowlist):
    for allowed in allowlist:
        if req.prefixlen == req.max_prefixlen and req.network_address in allowed:
            return True
        if req == allowed or req.subnet_of(allowed):
            return True
    return False

def run_check(org, client, secret):
    salesforce_ips = list(STATIC_CIDRS) + fetch_json_cidrs()
    sf_nets = to_networks(salesforce_ips)
    lb_ips = get_lb_cidrs("isc2", org, client, secret) + get_lb_cidrs("isc2-np", org, client, secret)
    lb_nets = to_networks(lb_ips)
    print("\n--- Salesforce required networks:")
    for net in sf_nets:
        print("  ", net)
    print("\n--- LB allowlist networks:")
    for net in lb_nets:
        print("  ", net)
    missing = [str(req) for req in sf_nets if not is_covered(req, lb_nets)]
    return missing

@app.route('/check-cidrs', methods=['GET', 'POST'])
def check_cidrs():
    if request.method == 'POST':
        data = request.get_json(force=True) or {}
        org = data.get("orgId")
        client = data.get("clientId")
        secret = data.get("clientSecret")
        if not (org and client and secret):
            return jsonify({"error": "Missing credentials"}), 400
        missing = run_check(org, client, secret)
        return jsonify({"missing_cidrs": missing})
    else:
        # GET: use environment variables (for Docker -e)
        org = os.getenv("ANYPOINT_ORG")
        client = os.getenv("ANYPOINT_CLIENT_ID")
        secret = os.getenv("ANYPOINT_CLIENT_SECRET")
        if not (org and client and secret):
            return jsonify({"error": "Server is missing credentials for GET"}), 500
        missing = run_check(org, client, secret)
        return jsonify({"missing_cidrs": missing})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
