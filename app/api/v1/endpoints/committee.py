"""Committee membership endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_committee_service, require_permission
from app.domain.committee import (
    CommitteeMemberNotFound,
    CommitteeMemberRecord,
    DuplicateCommitteeMember,
    UnknownCommitteeUser,
)
from app.schemas.committee import (
    AddCommitteeMemberRequest,
    CommitteeMemberListResponse,
    CommitteeMemberResponse,
)
from app.services.committee_service import CommitteeService

router = APIRouter(tags=["committee"])


def _member_response(member: CommitteeMemberRecord) -> CommitteeMemberResponse:
    return CommitteeMemberResponse(
        user_id=member.user_id,
        full_name=member.full_name,
        email=member.email,
    )


@router.get("/committee/members", response_model=CommitteeMemberListResponse)
def read_committee_members(
    service: CommitteeService = Depends(get_committee_service),
    _: object = Depends(require_permission("users", "view")),
) -> CommitteeMemberListResponse:
    """Return every committee member."""
    return CommitteeMemberListResponse(items=[_member_response(member) for member in service.list_members()])


@router.post("/committee/members", response_model=CommitteeMemberResponse, status_code=201)
def add_committee_member(
    body: AddCommitteeMemberRequest,
    service: CommitteeService = Depends(get_committee_service),
    _: object = Depends(require_permission("users", "create")),
) -> CommitteeMemberResponse:
    """Add an existing user to the committee."""
    try:
        member = service.add_member(body.user_id)
    except UnknownCommitteeUser as error:
        raise HTTPException(status_code=404, detail="User not found.") from error
    except DuplicateCommitteeMember as error:
        raise HTTPException(status_code=409, detail="User is already on the committee.") from error
    return _member_response(member)


@router.delete("/committee/members/{user_id}", status_code=204)
def remove_committee_member(
    user_id: str,
    service: CommitteeService = Depends(get_committee_service),
    _: object = Depends(require_permission("users", "create")),
) -> None:
    """Remove one user from the committee."""
    try:
        service.remove_member(user_id)
    except CommitteeMemberNotFound as error:
        raise HTTPException(status_code=404, detail="Committee member not found.") from error
