import httpx
import json
import os

api_key = os.getenv("IPOGURU_API_KEY")
if not api_key:
    print("ERROR: IPOGURU_API_KEY not set")
    exit(1)

response = httpx.get(
    "https://www.ipoguru.in/api/v1/ipos",
    headers={"X-API-KEY": api_key},
    params={"status": "open"},
    timeout=30.0,
)

print(f"Status: {response.status_code}")
data = response.json()
print(f"Success: {data.get('success')}")
print(f"Count: {data.get('count')}")
print(f"Plan: {data.get('plan')}")
print()

if data.get("data") and len(data["data"]) > 0:
    first = data["data"][0]
    print("=== First IPO keys ===")
    print(json.dumps(sorted(first.keys()), indent=2))
    print()
    print("=== First IPO full data ===")
    print(json.dumps(first, indent=2, default=str))
