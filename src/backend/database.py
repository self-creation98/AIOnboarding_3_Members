"""
Supabase client singleton.
Provides a single Supabase client instance for the entire application.
"""

from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

_supabase_client: Client | None = None


def get_supabase() -> Client:
    """
    Get or create the Supabase client.
    Uses service_role key for backend operations (bypasses RLS).
    """
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env. "
                "See .env.example for reference."
            )
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client
