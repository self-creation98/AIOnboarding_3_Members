"""Debug JWT — test truc tiep voi Supabase client."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from jose import jwt

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

print("=" * 60)
print("ENV CHECK")
print("=" * 60)
print(f"SUPABASE_URL: {SUPABASE_URL[:40]}...")
print(f"SUPABASE_KEY type: len={len(SUPABASE_KEY)}")
print(f"JWT_SECRET: '{JWT_SECRET[:15]}...' (len={len(JWT_SECRET)})")
print()

# Decode the Supabase key itself (it's a JWT!)
print("=== Decoding SUPABASE_KEY (anon/service_role) ===")
try:
    # The key itself is a JWT, decode without verification to see its payload
    key_payload = jwt.get_unverified_claims(SUPABASE_KEY)
    print(f"  Key role: {key_payload.get('role')}")
    print(f"  Key iss: {key_payload.get('iss')}")
    print(f"  -> This is a '{key_payload.get('role')}' key")
except Exception as e:
    print(f"  Cannot decode key: {e}")
print()

# Try login via Supabase directly
print("=== Supabase Auth: List users (admin) ===")
client = create_client(SUPABASE_URL, SUPABASE_KEY)
try:
    users = client.auth.admin.list_users()
    print(f"  Found {len(users)} users:")
    for u in users[:5]:
        print(f"    - {u.email} (confirmed: {bool(u.email_confirmed_at)})")
except Exception as e:
    print(f"  ERROR: {e}")
    print("  -> If 'not authorized', you're using anon key instead of service_role key")
print()

# Try signing in
print("=== Supabase Auth: Sign in ===")
test_email = "test@company.com"

# First, try to see what password format they used
try:
    # Try common passwords
    passwords_to_try = ["Test@123456", "test123456", "123456", "Test123456", "password"]
    for pwd in passwords_to_try:
        try:
            response = client.auth.sign_in_with_password({
                "email": test_email,
                "password": pwd,
            })
            if response.session:
                TOKEN = response.session.access_token
                print(f"  LOGIN SUCCESS with password: '{pwd}'")
                print(f"  Token: {TOKEN[:50]}...")
                print()

                # Now test JWT decode
                print("=== JWT Decode test ===")
                
                # First, peek at token without verification
                unverified = jwt.get_unverified_claims(TOKEN)
                print(f"  Token claims (unverified):")
                print(f"    email: {unverified.get('email')}")
                print(f"    aud:   {unverified.get('aud')}")
                print(f"    role:  {unverified.get('role')}")
                print(f"    sub:   {unverified.get('sub')}")
                print()

                # Try decode with JWT_SECRET
                print(f"  Trying decode with JWT_SECRET ('{JWT_SECRET[:10]}...')...")
                try:
                    verified = jwt.decode(TOKEN, JWT_SECRET, algorithms=["HS256"], audience="authenticated")
                    print(f"  => DECODE OK!")
                except Exception as e:
                    print(f"  => DECODE FAILED: {e}")
                    
                    # Try with the key header to find the right secret
                    header = jwt.get_unverified_header(TOKEN)
                    print(f"  Token header: {header}")
                    print()
                    print("  !!! Your SUPABASE_JWT_SECRET is likely wrong.")
                    print("  Find it at: Supabase Dashboard -> Settings -> API -> JWT Settings -> JWT Secret")
                    print("  It should be a long base64 string, NOT a UUID!")

                # Test protected endpoint
                print()
                print("=== Test protected endpoint with token ===")
                import httpx
                r = httpx.get(
                    "http://localhost:8000/api/employees",
                    headers={"Authorization": f"Bearer {TOKEN}"},
                    timeout=10,
                )
                print(f"  GET /api/employees: {r.status_code}")
                if r.status_code != 200:
                    print(f"  Response: {r.text[:300]}")
                else:
                    print(f"  Response: {r.text[:200]}")

                # Test create employee
                print()
                r2 = httpx.post(
                    "http://localhost:8000/api/employees",
                    headers={"Authorization": f"Bearer {TOKEN}"},
                    json={
                        "full_name": "Debug User",
                        "email": "debug@company.com",
                        "role": "Tester",
                        "department": "QA",
                        "start_date": "2026-04-15",
                    },
                    timeout=10,
                )
                print(f"  POST /api/employees: {r2.status_code}")
                print(f"  Response: {r2.text[:300]}")
                break
        except Exception:
            continue
    else:
        print(f"  Could not login with any test password for {test_email}")
        print("  Please check the password you set in Supabase Auth")
except Exception as e:
    print(f"  ERROR: {e}")
