import urllib.request, json, time

BASE = "https://skymaxx-lead-engine.onrender.com"
results = []

def test(name, url, expected_keys=None):
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=60)
        code = resp.getcode()
        body = resp.read().decode()
        try:
            data = json.loads(body)
            preview = json.dumps(data)[:200]
        except:
            data = None
            preview = body[:200]
        results.append(f"OK  | {name:30} | HTTP {code} | {preview}")
        return data
    except Exception as e:
        results.append(f"FAIL| {name:30} | {str(e)[:100]}")
        return None

print("Testing live app...")
test("Homepage HTML", BASE + "/")
stats = test("Stats endpoint", BASE + "/api/stats")
config = test("Config endpoint", BASE + "/api/config")
test("Cities endpoint", BASE + "/api/cities")
test("Sequence templates", BASE + "/api/sequence/templates")
test("Leads list", BASE + "/api/leads")
test("Send log", BASE + "/api/log")
test("Queue", BASE + "/api/sequence/queue")

# Detailed stats
if stats:
    results.append("")
    results.append("=== Current Stats ===")
    for k, v in stats.items():
        results.append(f"  {k}: {v}")

if config:
    results.append("")
    results.append("=== Config ===")
    for k, v in config.items():
        results.append(f"  {k}: {v}")

print("\n".join(results))
with open("e2e_test.txt", "w") as f:
    f.write("\n".join(results))
