"""Unit tests for client dependency purge rules."""

from types import SimpleNamespace

from sqlalchemy.sql import Delete

from app.repositories.client_purge import purge_client_dependencies


class FakeSession:
    def __init__(self, *, topic_ids: list[str], period_ids: list[str], user_ids: list[str]) -> None:
        self.topic_ids = topic_ids
        self.period_ids = period_ids
        self.user_ids = user_ids
        self.deletes: list[object] = []
        self.flushed = False

    def scalars(self, statement):  # noqa: ANN001
        sql = str(statement).lower()
        if "users" in sql:
            return SimpleNamespace(all=lambda: list(self.user_ids))
        if "periods" in sql:
            return SimpleNamespace(all=lambda: list(self.period_ids))
        if "topics" in sql:
            return SimpleNamespace(all=lambda: list(self.topic_ids))
        return SimpleNamespace(all=lambda: [])

    def execute(self, statement, params=None) -> None:  # noqa: ANN001
        self.deletes.append(statement)

    def flush(self) -> None:
        self.flushed = True


def test_purge_client_dependencies_removes_topics_and_committee_rows() -> None:
    session = FakeSession(topic_ids=["t-period"], period_ids=["p1"], user_ids=["u1"])
    purge_client_dependencies(session, "c1")
    assert session.flushed is True
    delete_sql = " ".join(str(item).lower() for item in session.deletes)
    assert "topics" in delete_sql
    assert "topic_opinion_reads" in delete_sql or "topicopinionread" in delete_sql
    assert "committee" in delete_sql
