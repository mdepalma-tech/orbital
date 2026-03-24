import os
from dotenv import load_dotenv

# Load .env.local in development; in production env vars are set directly
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))

SUPABASE_URL: str = os.environ.get("SUPABASE_URL") or os.environ["NEXT_PUBLIC_SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY: str = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
