import os
import sys

from dotenv import load_dotenv
from supabase import create_async_client

load_dotenv()

_url = os.getenv("SUPABASE_URL")
_key = os.getenv("SUPABASE_KEY")

if not _url or not _key:
    print("FATAL: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

_supabase_client = None


def get_client_credentials():
    return _url, _key


async def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = await create_async_client(_url, _key)
    return _supabase_client
