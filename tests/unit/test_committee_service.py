"""Unit tests for committee membership."""

from app.domain.committee import DuplicateCommitteeMember, UnknownCommitteeUser
from app.services.committee_service import CommitteeService
from tests.support.memory_committee_repository import InMemoryCommitteeRepository


def test_adds_an_existing_user_to_the_committee() -> None:
    repository = InMemoryCommitteeRepository()
    repository.seed_user("u1", "Ana Pérez", "ana@tucomite.local")
    service = CommitteeService(repository)

    member = service.add_member("u1")

    assert member.full_name == "Ana Pérez"
    assert service.list_members() == [member]


def test_rejects_unknown_and_duplicate_members() -> None:
    repository = InMemoryCommitteeRepository()
    repository.seed_user("u1", "Ana Pérez", "ana@tucomite.local")
    service = CommitteeService(repository)
    service.add_member("u1")

    try:
        service.add_member("missing")
        unknown_raised = False
    except UnknownCommitteeUser:
        unknown_raised = True

    try:
        service.add_member("u1")
        duplicate_raised = False
    except DuplicateCommitteeMember:
        duplicate_raised = True

    assert unknown_raised
    assert duplicate_raised
