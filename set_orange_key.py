
import urllib.request, json, sys

RENDER_KEY = "rnd_C7jBUGG8sEuBRvqf3U4w4YU4zWsx"
SERVICE_ID = "srv-d88vm9favr4c7396kt00"
ORANGE_KEY = "osk_2ebad93f315f7f54b13887e6f871391f95681071"

# Step 1: Get current env vars
req = urllib.request.Request(
    "https://api.render.com/v1/services/" + SERVICE_ID + "/env-vars?limit=100",
    headers={"Authorization": "Bearer " + RENDER_KEY, "Accept": "application/json"})
data = json.loads(urllib.request.urlopen(req).read())

current = []
for item in data:
    if isinstance(item, dict) and "envVar" in item:
        ev = item["envVar"]
        current.append({"key": ev["key"], "value": ev["value"]})

# Has ORANGESLICE_API_KEY already?
keys = [c["key"] for c in current]
print("Current env vars: " + ", ".join(sorted(keys)))

# Add or update ORANGESLICE_API_KEY
found = False
for c in current:
    if c["key"] == "ORANGESLICE_API_KEY":
        c["value"] = ORANGE_KEY
        found = True
if not found:
    current.append({"key": "ORANGESLICE_API_KEY", "value": ORANGE_KEY})

# PUT all env vars (this replaces the full set)
payload = json.dumps(current).encode()
req = urllib.request.Request(
    "https://api.render.com/v1/services/" + SERVICE_ID + "/env-vars",
    data=payload, method="PUT",
    headers={"Authorization": "Bearer " + RENDER_KEY,
             "Content-Type": "application/json",
             "Accept": "application/json"})
try:
    r = urllib.request.urlopen(req)
    print("PUT response: " + str(r.getcode()))
    print("ORANGESLICE_API_KEY " + ("UPDATED" if found else "ADDED"))
    print("Total vars now: " + str(len(current)))
except urllib.error.HTTPError as e:
    print("ERROR " + str(e.code) + ": " + e.read().decode()[:500])
    sys.exit(1)
