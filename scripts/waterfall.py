
import requests
import sys
import time
import os

# Standardize output for console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

BASE_URL = "http://127.0.0.1:8000"

def print_waterfall(timings):
    if not timings:
        print("No timing data available.")
        return

    # Sort nodes by start time
    sorted_nodes = sorted(timings.items(), key=lambda x: x[1]['start'])
    
    first_start = sorted_nodes[0][1]['start']
    last_end = max(node[1]['end'] for node in sorted_nodes)
    total_duration = last_end - first_start

    print("\n=== CHATBOT CALL WATERFALL ===")
    print(f"{'Node Name':<20} | {'Duration':<10} | {'Timeline'}")
    print("-" * 60)

    # Calculate width for timeline
    timeline_width = 40

    for name, data in sorted_nodes:
        duration = data['duration']
        start_offset = data['start'] - first_start
        
        # Scale positions
        start_pos = int((start_offset / total_duration) * timeline_width) if total_duration > 0 else 0
        bar_len = int((duration / total_duration) * timeline_width) if total_duration > 0 else 1
        if bar_len == 0: bar_len = 1
        
        timeline = " " * start_pos + "█" * bar_len
        print(f"{name[:20]:<20} | {duration:>8.4f}s | {timeline}")

    print("-" * 60)
    print(f"Total Graph Execution: {total_duration:.4f}s\n")

def run_test_query(query="Nghỉ thai sản là gì?"):
    # 1. Login
    print(f"[Waterfall] Logging in...")
    login_payload = {
        "username": "test@company.com",
        "password": "123456"
    }
    try:
        r = requests.post(f"{BASE_URL}/api/auth/login", data=login_payload)
    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to the server. Is it running?")
        return

    if r.status_code != 200:
        print(f"[Waterfall] Login failed: {r.text}")
        return
    
    auth_data = r.json()
    token = auth_data["access_token"]
    employee_id = auth_data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Chat
    print(f"[Waterfall] Sending query: '{query}'")
    chat_payload = {
        "employee_id": employee_id,
        "message": query
    }
    
    start_time = time.time()
    r = requests.post(f"{BASE_URL}/api/chat", json=chat_payload, headers=headers)
    total_latency = time.time() - start_time

    if r.status_code in [200, 201]:
        result = r.json()
        if result.get("success"):
            timings = result['data'].get('timings')
            print_waterfall(timings)
            print(f"Total API Latency (incl. network/overhead): {total_latency:.4f}s")
        else:
            print(f"Error in response: {result.get('error')}")
    else:
        print(f"HTTP Error {r.status_code}: {r.text}")

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "Nghỉ thai sản là gì?"
    run_test_query(query)
