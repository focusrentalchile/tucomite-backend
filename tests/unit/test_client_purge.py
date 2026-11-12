"""Unit tests for client dependency purge rules."""

from types import SimpleNamespace

from sqlalchemy.sql import Delete

from app.repositories.client_purge import purge_client_dependencies


class FakeSession:
    def __init__(self, topic_ids: list[str], period_ids: list[str]) -> None:
        self.topic_ids = topic_ids
        self.period_ids = period_ids
        self.deletes: list[Delete] = []
        self.flushed = False

    def scalars(self, statement):  # noqa: ANN001
        sql = str(statement)
        if "periods" in sql:
            return SimpleNamespace(all=lambda: list(self.period_ids))
        if "topics" in sql:
            return SimpleNamespace(all=lambda: list(self.topic_ids))
        return SimpleNamespace(all=lambda: [])

    def execute(self, statement) -> None:  # noqa: ANN001
        self.deletes.append(statement)

    def flush(self) -> None:
        self.flushed = True


def test_purge_client_dependencies_removes_topics_linked_by_period() -> None:
    session = FakeSession(topic_ids=["t-period"], period_ids=["p1"])
    purge_client_dependencies(session, "c1")
    assert session.flushed is True
    assert any("topics" in str(item).lower() for item in session.deletes)
