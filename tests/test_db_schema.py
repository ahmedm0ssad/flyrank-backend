import asyncpg
import pytest

DATABASE_URL = "postgresql://flyrank:flyrank_pass@127.0.0.1:5432/flyrank"

pytestmark = pytest.mark.asyncio

EXPECTED_TABLES = {"widgets", "leads", "rate_limits"}

EXPECTED_INDEXES = {
    "idx_widgets_tenant",
    "idx_widgets_domain",
    "idx_leads_widget",
    "idx_leads_tenant",
    "idx_leads_status",
    "idx_leads_spam",
    "idx_leads_fingerprint",
    "idx_leads_honeypot",
    "idx_rate_limits_lookup",
}


class TestDBSchema:
    async def test_tables_exist(self):
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            rows = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ANY($1::text[])
                ORDER BY table_name
                """,
                list(EXPECTED_TABLES),
            )
            found = {r["table_name"] for r in rows}
            missing = EXPECTED_TABLES - found
            assert not missing, f"Missing tables: {missing}"
        finally:
            await conn.close()

    async def test_indexes_exist(self):
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            rows = await conn.fetch("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename IN ('widgets', 'leads', 'rate_limits')
                ORDER BY indexname
                """)
            found = {r["indexname"] for r in rows}
            missing = EXPECTED_INDEXES - found
            assert not missing, f"Missing indexes: {missing}"
        finally:
            await conn.close()
