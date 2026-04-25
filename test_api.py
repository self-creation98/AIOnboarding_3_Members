"""Quick API test script."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests
import json

BASE = "http://127.0.0.1:8000"

def pp(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))

# --- 1. Login ---
print("=" * 60)
print("1. LOGIN")
print("=" * 60)
r = requests.post(f"{BASE}/api/auth/login", data={
    "username": "admin@company.com",
    "password": "123456",
})
print(f"Status: {r.status_code}")
login_data = r.json()
pp(login_data)

if r.status_code != 200:
    print("\nLogin failed. Trying hr@company.com...")
    r = requests.post(f"{BASE}/api/auth/login", data={
        "username": "hr@company.com",
        "password": "123456",
    })
    print(f"Status: {r.status_code}")
    login_data = r.json()
    pp(login_data)

if r.status_code != 200:
    print("\nCannot login. Check credentials.")
    sys.exit(1)

TOKEN = login_data["access_token"]
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
print(f"\nToken: {TOKEN[:30]}...")

# --- 2. List employees ---
print("\n" + "=" * 60)
print("2. LIST EMPLOYEES")
print("=" * 60)
r = requests.get(f"{BASE}/api/employees", headers=HEADERS)
print(f"Status: {r.status_code}")
emps = r.json()
if emps.get("success") and emps["data"]:
    for e in emps["data"][:3]:
        print(f"  - {e['id'][:8]}... {e['full_name']} ({e['department']}) - {e['onboarding_status']}")
    EMP_ID = emps["data"][0]["id"]
else:
    pp(emps)
    sys.exit(1)

# --- 3. Stakeholder tasks summary ---
print("\n" + "=" * 60)
print("3. STAKEHOLDER TASKS SUMMARY")
print("=" * 60)
r = requests.get(f"{BASE}/api/stakeholder-tasks/summary", headers=HEADERS)
print(f"Status: {r.status_code}")
pp(r.json())

# --- 4. List stakeholder tasks ---
print("\n" + "=" * 60)
print("4. LIST STAKEHOLDER TASKS")
print("=" * 60)
r = requests.get(f"{BASE}/api/stakeholder-tasks", headers=HEADERS)
print(f"Status: {r.status_code}")
tasks_data = r.json()
if tasks_data.get("success"):
    tasks = tasks_data["data"]
    print(f"  Total tasks: {len(tasks)}")
    for t in tasks[:5]:
        print(f"  - [{t['assigned_to_team']}] {t['title']} ({t['status']}) deadline={t.get('deadline')}")
else:
    pp(tasks_data)

# --- 5. Filter stakeholder tasks by team ---
print("\n" + "=" * 60)
print("5. FILTER TASKS BY TEAM=it")
print("=" * 60)
r = requests.get(f"{BASE}/api/stakeholder-tasks?assigned_to_team=it", headers=HEADERS)
print(f"Status: {r.status_code}")
pp(r.json())

print("\n" + "=" * 60)
print("ALL TESTS DONE")
print("=" * 60)
