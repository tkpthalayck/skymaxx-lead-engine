
import urllib.request, json

ORANGE_URL = "https://www.orangeslice.ai/mcp"
ORANGE_KEY = "osk_2ebad93f315f7f54b13887e6f871391f95681071"

def jsonrpc(method, params=None, id_=1):
    payload = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        payload["params"] = params
    req = urllib.request.Request(ORANGE_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + ORANGE_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=45)
        body = r.read().decode()
        ctype = r.headers.get("Content-Type", "")
        return r.getcode(), ctype, body
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type","?"), e.read().decode()
    except Exception as e:
        return 0, "?", str(e)

log = []
def L(m): log.append(str(m)); print(m, flush=True)

L("=== Orange Slice MCP Probe ===")
L("")
L("STEP 1: tools/list (no initialize)")
code, ctype, body = jsonrpc("tools/list", {})
L("  HTTP " + str(code) + " | Content-Type: " + ctype)
L("  Body (first 4000): " + body[:4000])
L("")

L("STEP 2: initialize handshake")
code, ctype, body = jsonrpc("initialize", {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "skymaxx-lead-engine", "version": "1.0.0"}
}, id_=99)
L("  HTTP " + str(code) + " | Content-Type: " + ctype)
L("  Body (first 2000): " + body[:2000])

# Parse session ID from SSE response if present
session_id = None
if "Mcp-Session-Id" in body or "mcp-session-id" in body:
    L("  Note: session ID header may be in response")

L("")
L("STEP 3: tools/list after initialize")
code, ctype, body = jsonrpc("tools/list", {}, id_=2)
L("  HTTP " + str(code) + " | Content-Type: " + ctype)
# Extract just the tool names if JSON
try:
    # Handle SSE format
    if "data: " in body:
        for line in body.split(chr(10)):
            if line.startswith("data: "):
                d = json.loads(line[6:])
                if "result" in d:
                    tools = d["result"].get("tools", [])
                    L("  Found " + str(len(tools)) + " tools:")
                    for t in tools[:30]:
                        L("    - " + str(t.get("name","?")) + ": " + str(t.get("description",""))[:120])
                    break
    else:
        d = json.loads(body)
        if "result" in d:
            tools = d["result"].get("tools", [])
            L("  Found " + str(len(tools)) + " tools:")
            for t in tools[:30]:
                L("    - " + str(t.get("name","?")) + ": " + str(t.get("description",""))[:120])
except Exception as e:
    L("  Parse error: " + str(e))
    L("  Raw body (first 3000): " + body[:3000])

open("orange_probe.txt","w").write(chr(10).join(log))
