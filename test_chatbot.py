
import requests
import sys
import time

# Standardize output for console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

BASE_URL = "http://127.0.0.1:8000"

def monitor_chatbot(interval_seconds=5):
    print("=== Chatbot Time Monitor ===")
    
    # 1. Login
    print("\n[Monitor] Logging in...")
    login_payload = {
        "username": "test@company.com",
        "password": "123456"
    }
    try:
        r = requests.post(f"{BASE_URL}/api/auth/login", data=login_payload)
    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to the server. Is it running?")
        print("Run: uvicorn src.backend.main:app --reload --port 8000")
        return

    if r.status_code != 200:
        print(f"[Monitor] Login failed: {r.text}")
        return
    
    auth_data = r.json()
    token = auth_data["access_token"]
    employee_id = auth_data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[Monitor] Login successful! User: {auth_data['user']['full_name']}")

    chat_payload = {
        "employee_id": employee_id,
        "message": "Nghỉ thai sản là gì?"
    }
    
    print(f"\n[Monitor] Starting continuous time monitor. Pinging every {interval_seconds} seconds. Press Ctrl+C to stop.")
    print(f"{'Time':<25} | {'Latency (s)':<12} | {'Status':<10} | {'Response Snippet'}")
    print("-" * 80)
    
    try:
        while True:
            start_time = time.time()
            try:
                r = requests.post(f"{BASE_URL}/api/chat", json=chat_payload, headers=headers)
                end_time = time.time()
                latency = end_time - start_time
                
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                snippet = ""
                if r.status_code in [200, 201]:
                    status = "OK"
                    result = r.json()
                    if result.get("success"):
                        answer = result['data']['answer']
                        snippet = answer[:30] + "..." if len(answer) > 30 else answer
                        snippet = snippet.replace('\n', ' ')
                    else:
                        snippet = "Error: " + str(result.get('error'))
                else:
                    status = f"ERR {r.status_code}"
                    snippet = r.text[:30].replace('\n', ' ')
                
                print(f"{timestamp:<25} | {latency:<12.4f} | {status:<10} | {snippet}")
                
            except requests.exceptions.ConnectionError:
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S'):<25} | {'N/A':<12} | {'CONN_ERR':<10} | Could not connect to server")
            
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n[Monitor] Stopped by user.")

if __name__ == "__main__":
    monitor_chatbot()

