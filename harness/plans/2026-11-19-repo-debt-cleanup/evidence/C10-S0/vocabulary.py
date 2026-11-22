"""C10-S0: compare contract.json with the PLANS.md target vocabulary and list error-code producers."""
import json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
APP = ROOT / "app"
contract = json.loads((APP / "desktop/protocol/v1/contract.json").read_text())
plans = (Path(__file__).resolve().parents[2] / "PLANS.md").read_text()
section = plans.split("## 目標詞彙", 1)[1].split("\n## ", 1)[0]
methods_block = section.split("**方法（25 個）**", 1)[1].split("**移除的方法", 1)[0]
target_methods = set(re.findall(r"`([a-z_]+\.[a-z_]+)`", methods_block))
events_block = section.split("**request event（8 個）**", 1)[1].split("**不變的部分", 1)[0]
target_events = set(re.findall(r"`([a-z_]+\.[a-z_]+)`", events_block))
methods = {item["name"] for item in contract["methods"]}
events = set(contract["requestEvents"])
print("methods", len(methods), "target", len(target_methods))
print("  contract-only:", sorted(methods - target_methods), " target-only:", sorted(target_methods - methods))
print("requestEvents", len(events), "target", len(target_events))
print("  contract-only:", sorted(events - target_events), " target-only:", sorted(target_events - events))
print("processEvents", len(contract["processEvents"]), sorted(contract["processEvents"]))
codes = contract["errorCodes"]
codes = list(codes) if isinstance(codes, (list, dict)) else []
print("errorCodes", len(codes))
for code in codes:
    py = subprocess.run(["grep", "-rn", "--include=*.py", f'"{code}"', str(APP / "agent"), str(APP / "skills"), str(APP / "rag")],
                        capture_output=True, text=True).stdout.splitlines()
    rs = subprocess.run(["grep", "-rn", f'"{code}"', str(APP / "desktop/src-tauri/src")], capture_output=True, text=True).stdout.splitlines()
    producers = [l for l in py + rs if "frozenset" not in l and "_SELF_EXPLANATORY" not in l]
    first = producers[0].replace(str(APP) + "/", "") .split(":")[0:2] if producers else ["—"]
    print(f"  {code}: python={len(py)} rust={len(rs)} producer={':'.join(first)}")
