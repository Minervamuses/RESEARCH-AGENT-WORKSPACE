"""Count valid/invalid shared fixtures per contract method (C3-S5 evidence)."""
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
contract = json.loads((root / "contract.json").read_text())
fixtures = json.loads((root / "fixtures.json").read_text())
counts = {m["name"]: {"valid": 0, "invalid": 0} for m in contract["methods"]}
def method_of_request(msg):
    if isinstance(msg, dict) and msg.get("messageType") == "request":
        return msg.get("method")
    return None
for case in fixtures["messages"]:
    m = method_of_request(case["message"])
    if m in counts:
        counts[m]["valid" if case["valid"] else "invalid"] += 1
for case in fixtures["traces"]:
    methods = {method_of_request(msg) for msg in case["messages"]} - {None}
    for m in methods:
        if m in counts:
            counts[m]["valid" if case["valid"] else "invalid"] += 1
missing = [m for m, c in counts.items() if c["valid"] == 0 or c["invalid"] == 0]
width = max(map(len, counts))
for m, c in counts.items():
    print(f"{m:<{width}}  valid={c['valid']:>3}  invalid={c['invalid']:>3}")
print(f"\nmethods: {len(counts)}; lacking a valid or an invalid fixture: {len(missing)}")
for m in missing:
    print("  MISSING", m, counts[m])
