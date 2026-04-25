import os
from dotenv import load_dotenv

load_dotenv()

# === AI Provider ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "claude-sonnet-4-20250514")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# === Supabase ===
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# === Auth ===
# Chỉ cho phép đăng nhập với email thuộc các domain này
ALLOWED_EMAIL_DOMAINS: list[str] = [
    d.strip() for d in os.getenv("ALLOWED_EMAIL_DOMAINS", "company.com").split(",")
    if d.strip()
]

# === Email Service ===
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "console")  # "resend" or "console"
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "onboarding@company.com")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "AI Onboarding System")

# === Magic Link ===
MAGIC_LINK_SECRET = os.getenv("MAGIC_LINK_SECRET", SUPABASE_JWT_SECRET or "change-me-in-production")
MAGIC_LINK_EXPIRY_HOURS = int(os.getenv("MAGIC_LINK_EXPIRY_HOURS", "168"))  # 7 ngày
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

