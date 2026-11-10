"""Closes a building owner's account after handing back everything in a ZIP."""

import uuid
from dataclasses import replace
from datetime import datetime, timezone

from app.domain.access import UserRecord
from app.domain.account import (
    CLIENT_ROLE_NAME,
    AccountAlreadyClosed,
    AccountClosureRequestRecord,
    AccountExport,
    AccountNotClient,
    InvalidAccountPassword,
)
from app.domain.messages import MessageRecord
from app.domain.periods import PeriodRecord
from app.repositories.access_repository import AccessRepository
from app.repositories.account_repository import AccountClosureRepository
from app.repositories.agreement_repository import AgreementRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.legal_repository import LegalRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.topic_repository import TopicRepository
from app.services.account_export import ArchiveBuilder, slug_with_id, slugify, to_plain
from app.utils.passwords import verify_password


class AccountService:
    """Verifies the owner, exports the building data, then soft-closes the account."""

    def __init__(
        self,
        *,
        access: AccessRepository,
        clients: ClientRepository,
        topics: TopicRepository,
        agreements: AgreementRepository,
        periods: PeriodRepository,
        closures: AccountClosureRepository,
        legal: LegalRepository | None = None,
        messages: MessageRepository | None = None,
        projects: ProjectRepository | None = None,
    ) -> None:
        self._access = access
        self._clients = clients
        self._topics = topics
        self._agreements = agreements
        self._periods = periods
        self._closures = closures
        self._legal = legal
        self._messages = messages
        self._projects = projects

    def close_account(self, user_id: str, reason: str, password: str) -> AccountExport:
        """Close the owner's account and return the ZIP of the building's data.

        The ZIP is fully built before anything is changed. Only then the closure request is
        stored and the user is flagged closed (the row stays, so history keeps its author).
        """
        user = self._access.get_user(user_id)
        role = self._access.get_role(user.role_id) if user is not None else None
        if (
            user is None
            or role is None
            or role.system
            or role.name.strip().casefold() != CLIENT_ROLE_NAME
        ):
            raise AccountNotClient()
        if user.account_closed_at:
            raise AccountAlreadyClosed()
        if not verify_password(password, user.password_hash):
            raise InvalidAccountPassword()
        cleaned_reason = reason.strip()
        if not cleaned_reason:
            raise ValueError("A reason is required.")

        now = datetime.now(timezone.utc)
        export = self.build_export(user, now)
        self._closures.add(
            AccountClosureRequestRecord(
                id=str(uuid.uuid4()),
                user_id=user.id,
                client_id=user.client_id,
                reason=cleaned_reason[:2000],
                created_at=now.isoformat(),
            ),
        )
        self._access.close_user_account(user.id, now.isoformat())
        return export

    def build_export(self, user: UserRecord, now: datetime | None = None) -> AccountExport:
        """Build the ZIP with agreements/, topics/, documents/, users/, and messages/."""
        moment = now or datetime.now(timezone.utc)
        client_id = user.client_id
        client = self._clients.get_client(client_id) if client_id else None
        archive = ArchiveBuilder()

        period_list = self._periods.list_periods(client_id) if client_id else []
        period_ids = {period.id for period in period_list}
        counts = {
            "agreements": self._export_agreements(archive, client_id),
            "topics": self._export_topics(archive, client_id, period_ids),
            "documents": self._export_documents(archive, client_id, period_list),
            "users": self._export_users(archive, client_id),
            "messages": self._export_messages(archive, client_id),
        }
        archive.add_json(
            "manifest.json",
            {
                "building": client.name if client is not None else "",
                "client_id": client_id,
                "exported_at": moment.isoformat(),
                "exported_by": {"id": user.id, "full_name": user.full_name, "email": user.email},
                "periods": [{"id": item.id, "name": item.name, "status": item.status} for item in period_list],
                "counts": counts,
            },
        )
        building = slugify(client.name, "edificio") if client is not None else "edificio"
        filename = f"tu-comite-{building}-{moment:%Y%m%d}.zip"
        return AccountExport(filename=filename, content=archive.finish())

    def _export_agreements(self, archive: ArchiveBuilder, client_id: str | None) -> int:
        if not client_id:
            return 0
        items = self._agreements.list_agreements(client_id=client_id)
        for item in items:
            base = f"agreements/{slug_with_id(item.title, item.id)}"
            archive.add_json(f"{base}.json", item)
            detail = self._agreements.get(item.id)
            if detail is not None and detail.pdf_bytes:
                archive.add_bytes(f"{base}.pdf", detail.pdf_bytes)
        return len(items)

    def _export_topics(
        self,
        archive: ArchiveBuilder,
        client_id: str | None,
        period_ids: set[str],
    ) -> int:
        if not client_id:
            return 0
        topics = [
            topic
            for topic in self._topics.list_topics()
            if topic.client_id == client_id or topic.period_id in period_ids
        ]
        topic_ids = [topic.id for topic in topics]
        votes = self._topics.list_votes_for_topics(topic_ids)
        opinions = self._topics.list_opinions_for_topics(topic_ids)
        confirmations = self._topics.list_confirmations_for_topics(topic_ids)
        attachments = self._topics.list_attachments_for_topics(topic_ids)
        completion = self._topics.list_completion_attachments_for_topics(topic_ids)
        for topic in topics:
            folder = f"topics/{slug_with_id(topic.title, topic.id)}"
            files = archive.add_attachments(
                folder,
                [item for item in attachments if item.topic_id == topic.id],
            )
            completion_files = archive.add_attachments(
                f"{folder}/completion",
                [item for item in completion if item.topic_id == topic.id],
            )
            archive.add_json(
                f"{folder}/topic.json",
                {
                    "topic": topic,
                    "votes": [item for item in votes if item.topic_id == topic.id],
                    "opinions": [item for item in opinions if item.topic_id == topic.id],
                    "confirmations": [item for item in confirmations if item.topic_id == topic.id],
                    "attachments": files,
                    "completion_attachments": completion_files,
                },
            )
        return len(topics)

    def _export_documents(
        self,
        archive: ArchiveBuilder,
        client_id: str | None,
        period_list: list[PeriodRecord],
    ) -> int:
        count = 0
        if client_id and self._legal is not None:
            cases = self._legal.list_cases(client_id)
            case_attachments = self._legal.list_attachments_for_cases([case.id for case in cases])
            for case in cases:
                folder = f"documents/legal/{slug_with_id(case.title, case.id)}"
                files = archive.add_attachments(
                    folder,
                    [item for item in case_attachments if item.case_id == case.id],
                )
                archive.add_json(
                    f"{folder}/case.json",
                    {"case": case, "messages": self._legal.list_messages(case.id), "attachments": files},
                )
                count += 1
        if self._projects is not None:
            for period in period_list:
                projects = self._projects.list_projects(period.id)
                project_attachments = self._projects.list_attachments_for_projects(
                    [project.id for project in projects],
                )
                for project in projects:
                    folder = f"documents/projects/{slug_with_id(project.title, project.id)}"
                    files = archive.add_attachments(
                        folder,
                        [item for item in project_attachments if item.project_id == project.id],
                    )
                    archive.add_json(
                        f"{folder}/project.json",
                        {"project": project, "period": period.name, "attachments": files},
                    )
                    count += 1
        return count

    def _export_users(self, archive: ArchiveBuilder, client_id: str | None) -> int:
        if not client_id:
            return 0
        roles = {role.id: role.name for role in self._access.list_roles()}
        summary = [
            {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "role": roles.get(user.role_id, ""),
                "floor_number": user.floor_number,
                "apartment_number": user.apartment_number,
                "account_closed_at": user.account_closed_at,
            }
            for user in self._access.list_users()
            if user.client_id == client_id
        ]
        archive.add_json("users/summary.json", summary)
        return len(summary)

    def _export_messages(self, archive: ArchiveBuilder, client_id: str | None) -> int:
        if not client_id or self._messages is None:
            return 0
        items = self._messages.list_messages_for_client(client_id)
        for message in items:
            folder = f"messages/{slug_with_id(message.subject, message.id)}"
            archive.add_json(f"{folder}/message.json", self._message_payload(archive, folder, message))
        return len(items)

    def _message_payload(self, archive: ArchiveBuilder, folder: str, message: MessageRecord) -> dict:
        """Message JSON whose attachments point at the files extracted into the archive."""
        files = archive.add_attachments(folder, message.attachments)
        replies = []
        for reply in message.replies:
            reply_files = archive.add_attachments(f"{folder}/replies/{reply.id[:8]}", reply.attachments)
            replies.append({**to_plain(replace(reply, attachments=())), "attachments": reply_files})
        payload = to_plain(replace(message, attachments=(), replies=()))
        payload["attachments"] = files
        payload["replies"] = replies
        return payload
