"""Unit tests for committee membership enrollment."""

from app.services.committee_access import ensure_committee_access, is_listed_committee_member
from tests.support.memory_committee_repository import InMemoryCommitteeRepository


class _FakeSession:
    """Holds the in-memory committee repo used by SqlCommitteeRepository patching."""

    def __init__(self, repo: InMemoryCommitteeRepository) -> None:
        self.repo = repo


def test_client_role_is_enrolled_as_committee_voter(monkeypatch) -> None:
    repo = InMemoryCommitteeRepository()

    class _Repo:
        def __init__(self, _session) -> None:
            self._inner = repo

        def get_member(self, user_id: str):
            return self._inner.get_member(user_id)

        def add_member(self, user_id: str) -> None:
            self._inner.add_member(user_id)

        def remove_member(self, user_id: str) -> None:
            self._inner.remove_member(user_id)

    monkeypatch.setattr(
        "app.services.committee_access.SqlCommitteeRepository",
        _Repo,
    )
    repo.seed_user("owner-1", "Cliente", "client@tucomite.cl")
    session = object()
    assert ensure_committee_access(session, "owner-1", "client", frozenset({"agreements.vote"}))
    assert is_listed_committee_member(session, "owner-1")
    assert "owner-1" in repo.member_ids
