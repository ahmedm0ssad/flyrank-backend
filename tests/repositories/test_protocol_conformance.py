from app.repositories.lead_repo import LeadRepository
from app.repositories.postgres_lead_repo import PostgresLeadRepository
from app.repositories.postgres_widget_repo import PostgresWidgetRepository
from app.repositories.protocol import (
    LeadRepositoryProtocol,
    WidgetRepositoryProtocol,
)
from app.repositories.widget_repo import WidgetRepository


class TestProtocolConformance:
    def test_lead_repository_conforms_to_protocol(self):
        repo = LeadRepository()
        assert isinstance(repo, LeadRepositoryProtocol)

    def test_postgres_lead_repository_conforms_to_protocol(self):
        repo = PostgresLeadRepository()
        assert isinstance(repo, LeadRepositoryProtocol)

    def test_widget_repository_conforms_to_protocol(self):
        repo = WidgetRepository()
        assert isinstance(repo, WidgetRepositoryProtocol)

    def test_postgres_widget_repository_conforms_to_protocol(self):
        repo = PostgresWidgetRepository()
        assert isinstance(repo, WidgetRepositoryProtocol)
