"""Find the newest, fastest mainnet full snapshot served by a public RPC node and download it."""
import json, re, subprocess, sys, time, urllib.request, concurrent.futures as cf
OUT = sys.argv[1] if len(sys.argv) > 1 else "/crekk/snapshot"
def rpc(method, params=None):
    req = urllib.request.Request("https://api.mainnet-beta.solana.com", method="POST",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))["result"]
slot = rpc("getSlot")
nodes = [n["rpc"] for n in rpc("getClusterNodes") if n.get("rpc")]
print(f"slot {slot}, {len(nodes)} rpc nodes", flush=True)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
opener = urllib.request.build_opener(NoRedirect)
def probe(addr):
    try:
        opener.open(urllib.request.Request(f"http://{addr}/snapshot.tar.bz2", method="HEAD"), timeout=3)
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "")
        m = re.search(r"snapshot-(\d+)-(\w+)\.tar\.(zst|bz2)", loc)
        if m: return addr, int(m.group(1)), loc
    except Exception: pass
    return None
with cf.ThreadPoolExecutor(200) as ex:
    found = [r for r in ex.map(probe, nodes) if r]
found = [f for f in found if slot - f[1] < 150_000]
print(f"{len(found)} nodes serve a recent full snapshot", flush=True)
newest = max(f[1] for f in found)
cands = [f for f in found if f[1] == newest] or found
def speed(f):
    addr, s, loc = f
    url = f"http://{addr}{loc}" if loc.startswith("/") else loc
    try:
        r = urllib.request.urlopen(url, timeout=5); t = time.time(); n = 0
        while time.time() - t < 8:
            b = r.read(1 << 20)
            if not b: break
            n += len(b)
        return n / (time.time() - t) / 1e6, url
    except Exception: return 0, url
with cf.ThreadPoolExecutor(8) as ex:
    ranked = sorted(ex.map(speed, cands[:24]), reverse=True)
for mbps, url in ranked[:5]: print(f"{mbps:7.1f} MB/s {url}", flush=True)
mbps, url = ranked[0]
import os
if os.environ.get("DRY"): sys.exit(0)
name = url.rsplit("/", 1)[1]
subprocess.run(["aria2c", "-x16", "-s16", "--file-allocation=none", "--summary-interval=60",
                "-d", OUT, "-o", name, url], check=True)
print("SNAPSHOT DONE", OUT + "/" + name)
