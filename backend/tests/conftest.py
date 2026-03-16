"""
Stub out heavy external dependencies that require infrastructure (Supabase,
psycopg2, redis) so unit tests can import backend modules without a live DB.
"""
import sys
from unittest.mock import MagicMock

# Stub backend.database entirely — it calls os.environ at import time and
# requires a live Supabase + Postgres connection, neither of which is
# available in unit-test runs.
_db_mock = MagicMock()
_db_mock.get_conn.return_value = MagicMock()
_db_mock.release_conn.return_value = None
_db_mock.set_org_context.return_value = None
sys.modules["backend.database"] = _db_mock

# redis — patched per-test, but must be importable at module level
sys.modules.setdefault("redis", MagicMock())
