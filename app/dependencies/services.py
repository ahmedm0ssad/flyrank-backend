from app.repositories.lead_repo import LeadRepository
from app.repositories.widget_repo import WidgetRepository

_lead_repo: LeadRepository | None = None
_widget_repo: WidgetRepository | None = None
_redis = None


def get_lead_repo() -> LeadRepository:
    global _lead_repo
    if _lead_repo is None:
        _lead_repo = LeadRepository()
    return _lead_repo


def get_widget_repo() -> WidgetRepository:
    global _widget_repo
    if _widget_repo is None:
        from app.core.database import is_postgres_enabled

        if is_postgres_enabled():
            from app.repositories.postgres_widget_repo import (
                PostgresWidgetRepository,
            )

            _widget_repo = PostgresWidgetRepository()
        else:
            _widget_repo = WidgetRepository()
    return _widget_repo


async def get_redis():
    global _redis
    if _redis is None:
        try:
            from app.main import get_redis as _get_main_redis

            _redis = _get_main_redis()
        except (ImportError, RuntimeError):
            pass
    return _redis
