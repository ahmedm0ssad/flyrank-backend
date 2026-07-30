import json
from datetime import datetime, timezone
from typing import Any

from app.core.database import get_pool
from app.models.widget import WidgetResponse
from app.repositories.protocol import WidgetRepositoryProtocol


class PostgresWidgetRepository(WidgetRepositoryProtocol):
    @staticmethod
    def _row_to_response(row) -> WidgetResponse:
        return WidgetResponse(
            id=row["id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            domain=row["domain"],
            config=(
                row["config"]
                if isinstance(row["config"], dict)
                else json.loads(row["config"])
            ),
            js_version=row["js_version"],
            active=row["active"],
            created_at=row["created_at"],
        )

    async def create(
        self,
        name: str,
        domain: str,
        config: dict[str, Any],
        tenant_id: str,
    ) -> WidgetResponse:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO widgets (tenant_id, name, domain, config, created_at, updated_at)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                RETURNING id, tenant_id, name, domain, config, js_version, active, created_at
                """,
                tenant_id,
                name,
                domain,
                json.dumps(config),
                now,
                now,
            )
        return self._row_to_response(row)

    async def get_by_id(self, widget_id: str, tenant_id: str) -> WidgetResponse | None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, tenant_id, name, domain, config, js_version, active, created_at
                FROM widgets WHERE id = $1 AND tenant_id = $2 AND active = TRUE
                """,
                widget_id,
                tenant_id,
            )
        if row is None:
            return None
        return self._row_to_response(row)

    async def get_by_id_raw(self, widget_id: str) -> dict | None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, tenant_id, name, domain, config, js_version, active, created_at, updated_at
                FROM widgets WHERE id = $1
                """,
                widget_id,
            )
        if row is None:
            return None
        result = dict(row)
        if isinstance(result.get("config"), str):
            result["config"] = json.loads(result["config"])
        return result

    async def list_by_tenant(
        self,
        tenant_id: str,
        search: str | None = None,
        active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WidgetResponse], int]:
        pool = await get_pool()
        conditions = ["tenant_id = $1"]
        params = [tenant_id]
        param_idx = 2

        if search is not None:
            conditions.append(f"name ILIKE ${param_idx}")
            params.append(f"%{search}%")
            param_idx += 1
        if active is not None:
            conditions.append(f"active = ${param_idx}")
            params.append(active)
            param_idx += 1

        where = " AND ".join(conditions)
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM widgets WHERE {where}", *params
            )
            rows = await conn.fetch(
                f"""
                SELECT id, tenant_id, name, domain, config, js_version, active, created_at
                FROM widgets WHERE {where}
                ORDER BY created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
                """,
                *params,
                page_size,
                (page - 1) * page_size,
            )
        items = [self._row_to_response(r) for r in rows]
        return items, count

    async def update(
        self,
        widget_id: str,
        tenant_id: str,
        name: str | None = None,
        domain: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> WidgetResponse | None:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT config FROM widgets WHERE id = $1 AND tenant_id = $2",
                widget_id,
                tenant_id,
            )
            if existing is None:
                return None

            raw_config = existing["config"]
            if isinstance(raw_config, str):
                raw_config = json.loads(raw_config)
            merged_config = dict(raw_config)
            if config is not None:
                merged_config.update(config)

            row = await conn.fetchrow(
                """
                UPDATE widgets
                SET name = COALESCE($3, name),
                    domain = COALESCE($4, domain),
                    config = $5::jsonb,
                    js_version = js_version + 1,
                    updated_at = $6
                WHERE id = $1 AND tenant_id = $2
                RETURNING id, tenant_id, name, domain, config, js_version, active, created_at
                """,
                widget_id,
                tenant_id,
                name,
                domain,
                json.dumps(merged_config),
                now,
            )
        if row is None:
            return None
        return self._row_to_response(row)

    async def soft_delete(self, widget_id: str, tenant_id: str) -> bool:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE widgets SET active = FALSE, updated_at = $3 WHERE id = $1 AND tenant_id = $2",
                widget_id,
                tenant_id,
                now,
            )
        return result != "UPDATE 0"

    async def check_domain_exists(
        self, domain: str, tenant_id: str, exclude_id: str | None = None
    ) -> bool:
        pool = await get_pool()
        async with pool.acquire() as conn:
            if exclude_id:
                row = await conn.fetchrow(
                    """
                    SELECT 1 FROM widgets
                    WHERE tenant_id = $1 AND domain = $2 AND id != $3 AND active = TRUE
                    """,
                    tenant_id,
                    domain,
                    exclude_id,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT 1 FROM widgets
                    WHERE tenant_id = $1 AND domain = $2 AND active = TRUE
                    """,
                    tenant_id,
                    domain,
                )
        return row is not None
