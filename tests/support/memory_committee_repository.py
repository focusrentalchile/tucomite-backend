"""In-memory committee repository for unit tests."""

from app.domain.committee import CommitteeMemberRecord


class InMemoryCommitteeRepository:
    """Stores committee members without MySQL."""

    def __init__(self) -> None:
        self.users: dict[str, CommitteeMemberRecord] = {}
        self.member_ids: set[str] = set()

    def seed_user(self, user_id: str, full_name: str, email: str) -> None:
        self.users[user_id] = CommitteeMemberRecord(user_id=user_id, full_name=full_name, email=email)

    def list_members(self) -> list[CommitteeMemberRecord]:
        return sorted(
            [self.users[user_id] for user_id in self.member_ids if user_id in self.users],
            key=lambda member: member.full_name,
        )

    def get_member(self, user_id: str) -> CommitteeMemberRecord | None:
        if user_id not in self.member_ids:
            return None
        return self.users.get(user_id)

    def add_member(self, user_id: str) -> None:
        self.member_ids.add(user_id)

    def remove_member(self, user_id: str) -> None:
        self.member_ids.discard(user_id)

    def get_user_profile(self, user_id: str) -> CommitteeMemberRecord | None:
        return self.users.get(user_id)
