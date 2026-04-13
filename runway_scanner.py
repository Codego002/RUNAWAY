# runway_scanner.py - TEST SANS UNICODE

print("MINIMAL ADDON STARTED")

def request(flow):
    host = flow.request.pretty_host
    if "runwayml.com" in host or "api.runwayml.com" in host:
        path = flow.request.path
        method = flow.request.method
        print(f"REQ {method} {path}")

def response(flow):
    if "runwayml.com" in flow.request.pretty_host or "api.runwayml.com" in flow.request.pretty_host:
        print(f"RESP {flow.response.status_code} {flow.request.path}")