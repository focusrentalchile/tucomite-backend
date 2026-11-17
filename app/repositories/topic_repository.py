"""Persistence for topic statuses, topics, and votes."""

import json
from datetime import date, datetime, timezone
from typing import Protocol

from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app.domain.topics import (
    CLOSED_STATUS_ID,
    VOTE_TYPE_YES_NO,
    StatusRecord,
    TopicAttachmentRecord,
    TopicCompletionRoundRecord,
    TopicConfirmationRecord,
    TopicOpinionRecord,
    TopicRecord,
    TopicVoteOptionRecord,
    TopicVoteRecord,
)
from app.models.topics import (
    StatusModel,
    TopicAttachmentModel,
    TopicCompletionAttachmentModel,
    TopicConfirmationModel,
    TopicModel,
    TopicOpinionModel,
    TopicVoteModel,
)


def _to_naive_utc(value: str | None) -> datetime | None:
    """Convert a stored UTC ISO string into the naive UTC datetime MySQL keeps."""
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _to_utc_iso(value: datetime | None) -> str | None:
    """Return a naive UTC datetime read from MySQL as an aware ISO-8601 string."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class TopicRepository(Protocol):
    """Persistence port used by the topic service."""

    def list_statuses(self) -> list[StatusRecord]:
        """Return every status in id order."""

    def add_status(self, status: StatusRecord) -> None:
        """Insert one status."""

    def save_status(self, status: StatusRecord) -> None:
        """Update the key stored for one status id."""

    def add_topic(self, topic: TopicRecord) -> None:
        """Insert one topic."""

    def get_topic(self, topic_id: str) -> TopicRecord | None:
        """Return one topic by id."""

    def save_topic_status(self, topic_id: str, status_id: int) -> None:
        """Update the board column for one topic."""

    def save_topic(self, topic: TopicRecord) -> None:
        """Update the editable fields for one topic."""

    def delete_topic(self, topic_id: str) -> None:
        """Remove one topic and its votes."""

    def list_topics(self) -> list[TopicRecord]:
        """Return every topic."""

    def list_votes(self, topic_id: str) -> list[TopicVoteRecord]:
        """Return every vote for one topic."""

    def list_votes_for_topics(self, topic_ids: list[str]) -> list[TopicVoteRecord]:
        """Return every vote belonging to the given topics."""

    def get_vote(self, topic_id: str, author_id: str) -> TopicVoteRecord | None:
        """Return the vote cast by one author on one topic."""

    def add_vote(self, vote: TopicVoteRecord) -> None:
        """Insert one vote."""

    def save_vote(self, vote: TopicVoteRecord) -> None:
        """Update the choice stored for one vote."""

    def list_opinions_for_topics(self, topic_ids: list[str]) -> list[TopicOpinionRecord]:
        """Return every opinion belonging to the given topics."""

    def get_opinion(self, topic_id: str, author_id: str) -> TopicOpinionRecord | None:
        """Return the opinion written by one author on one topic."""

    def add_opinion(self, opinion: TopicOpinionRecord) -> None:
        """Insert one opinion."""

    def save_opinion(self, opinion: TopicOpinionRecord) -> None:
        """Update the body stored for one opinion."""

    def list_attachments_for_topics(self, topic_ids: list[str]) -> list[TopicAttachmentRecord]:
        """Return every attachment belonging to the given topics."""

    def replace_attachments(self, topic_id: str, attachments: list[TopicAttachmentRecord]) -> None:
        """Replace every attachment for one topic."""

    def save_topic_completion(self, topic: TopicRecord) -> None:
        """Store completion note and submitted timestamp."""

    def list_completion_attachments_for_topics(
        self,
        topic_ids: list[str],
    ) -> list[TopicAttachmentRecord]:
        """Return completion evidence attachments for the given topics."""

    def replace_completion_attachments(
        self,
        topic_id: str,
        attachments: list[TopicAttachmentRecord],
    ) -> None:
        """Replace completion evidence attachments for one topic."""

    def list_confirmations_for_topics(self, topic_ids: list[str]) -> list[TopicConfirmationRecord]:
        """Return every completion confirmation for the given topics."""

    def get_confirmation(self, topic_id: str, author_id: str) -> TopicConfirmationRecord | None:
        """Return one author's confirmation on one topic."""

    def add_confirmation(self, confirmation: TopicConfirmationRecord) -> None:
        """Insert one completion confirmation."""

    def clear_confirmations_for_topic(self, topic_id: str) -> None:
        """Remove every Resultado vote for the current open round."""


class SqlTopicRepository:
    """SQLAlchemy adapter for the MySQL topic tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_statuses(self) -> list[StatusRecord]:
        rows = self._session.scalars(select(StatusModel).order_by(StatusModel.id)).all()
        return [StatusRecord(id=row.id, key=row.key) for row in rows]

    def add_status(self, status: StatusRecord) -> None:
        self._session.add(StatusModel(id=status.id, key=status.key))

    def save_status(self, status: StatusRecord) -> None:
        row = self._session.get(StatusModel, status.id)
        if row is not None:
            row.key = status.key

    def add_topic(self, topic: TopicRecord) -> None:
        self._session.add(
            TopicModel(
                id=topic.id,
                title=topic.title,
                description=topic.description,
                category_key=topic.category_key,
                attachment_name=topic.attachment_name,
                decision=topic.decision,
                vote_type=topic.vote_type or VOTE_TYPE_YES_NO,
                vote_options_json=self._options_json(topic.vote_options),
                status_id=topic.status_id,
                priority_id=topic.priority_id,
                assignee_user_id=topic.assignee_user_id,
                start_date=date.fromisoformat(topic.start_date) if topic.start_date else None,
                due_date=date.fromisoformat(topic.due_date) if topic.due_date else None,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                status_entered_at=datetime.now(timezone.utc).replace(tzinfo=None),
                closed_at=None,
                period_id=topic.period_id,
                completion_note=topic.completion_note,
                completion_submitted_at=(
                    datetime.fromisoformat(topic.completion_submitted_at)
                    if topic.completion_submitted_at
                    else None
                ),
                client_id=topic.client_id,
                voting_starts_at=_to_naive_utc(topic.voting_starts_at),
                voting_ends_at=_to_naive_utc(topic.voting_ends_at),
            ),
        )
        # Attachments, votes, and opinions reference this row by foreign key only (no ORM
        # relationship), so the unit of work does not order their inserts after it.
        self._session.flush()

    def get_topic(self, topic_id: str) -> TopicRecord | None:
        row = self._session.get(TopicModel, topic_id)
        if row is None:
            return None
        if getattr(row, "deleted_at", None) is not None:
            return None
        return self._topic(row)

    def save_topic_status(self, topic_id: str, status_id: int) -> None:
        row = self._session.get(TopicModel, topic_id)
        if row is not None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            row.status_id = status_id
            if hasattr(row, "status_entered_at"):
                row.status_entered_at = now
            if status_id == CLOSED_STATUS_ID:
                row.closed_at = now
            else:
                row.closed_at = None

    def save_topic(self, topic: TopicRecord) -> None:
        row = self._session.get(TopicModel, topic.id)
        if row is None:
            return
        row.title = topic.title
        row.description = topic.description
        row.category_key = topic.category_key
        row.attachment_name = topic.attachment_name
        row.decision = topic.decision
        if hasattr(row, "vote_type"):
            row.vote_type = topic.vote_type or VOTE_TYPE_YES_NO
        if hasattr(row, "vote_options_json"):
            row.vote_options_json = self._options_json(topic.vote_options)
        row.status_id = topic.status_id
        row.priority_id = topic.priority_id
        row.assignee_user_id = topic.assignee_user_id
        row.start_date = date.fromisoformat(topic.start_date) if topic.start_date else None
        row.due_date = date.fromisoformat(topic.due_date) if topic.due_date else None
        row.period_id = topic.period_id
        row.client_id = topic.client_id
        row.voting_starts_at = _to_naive_utc(topic.voting_starts_at)
        row.voting_ends_at = _to_naive_utc(topic.voting_ends_at)
        row.completion_note = topic.completion_note
        row.completion_submitted_at = (
            datetime.fromisoformat(topic.completion_submitted_at)
            if topic.completion_submitted_at
            else None
        )

    def save_topic_assignment(
        self,
        topic_id: str,
        assignee_user_id: str,
        due_date: str,
        start_date: str | None = None,
    ) -> None:
        """Store the person responsible and the execution dates."""
        row = self._session.get(TopicModel, topic_id)
        if row is None:
            return
        row.assignee_user_id = assignee_user_id
        row.start_date = date.fromisoformat(start_date) if start_date else None
        row.due_date = date.fromisoformat(due_date)

    def save_topic_completion(self, topic: TopicRecord) -> None:
        row = self._session.get(TopicModel, topic.id)
        if row is None:
            return
        row.completion_note = topic.completion_note
        row.completion_submitted_at = (
            datetime.fromisoformat(topic.completion_submitted_at)
            if topic.completion_submitted_at
            else None
        )
        if hasattr(row, "completion_round"):
            row.completion_round = max(1, int(topic.completion_round or 1))
        if hasattr(row, "completion_rounds_json"):
            row.completion_rounds_json = self._rounds_json(topic.completion_rounds)

    def delete_topic(self, topic_id: str) -> None:
        """Passive archive: mark deleted_at so the board hides the topic."""
        row = self._session.get(TopicModel, topic_id)
        if row is None:
            return
        if hasattr(row, "deleted_at"):
            row.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
            self._session.flush()
            return
        self._session.execute(delete(TopicVoteModel).where(TopicVoteModel.topic_id == topic_id))
        bind = self._session.get_bind()
        if bind is not None and inspect(bind).has_table("topic_opinions"):
            self._session.execute(
                delete(TopicOpinionModel).where(TopicOpinionModel.topic_id == topic_id),
            )
        if bind is not None and inspect(bind).has_table("topic_attachments"):
            self._session.execute(
                delete(TopicAttachmentModel).where(TopicAttachmentModel.topic_id == topic_id),
            )
        if bind is not None and inspect(bind).has_table("topic_completion_attachments"):
            self._session.execute(
                delete(TopicCompletionAttachmentModel).where(
                    TopicCompletionAttachmentModel.topic_id == topic_id,
                ),
            )
        if bind is not None and inspect(bind).has_table("topic_confirmations"):
            self._session.execute(
                delete(TopicConfirmationModel).where(TopicConfirmationModel.topic_id == topic_id),
            )
        self._session.delete(row)

    def list_topics(self) -> list[TopicRecord]:
        rows = self._session.scalars(select(TopicModel).order_by(TopicModel.title)).all()
        return [
            self._topic(row)
            for row in rows
            if getattr(row, "deleted_at", None) is None
        ]

    def list_votes(self, topic_id: str) -> list[TopicVoteRecord]:
        rows = self._session.scalars(
            select(TopicVoteModel)
            .where(TopicVoteModel.topic_id == topic_id)
            .order_by(TopicVoteModel.author_name),
        ).all()
        return [self._vote(row) for row in rows]

    def list_votes_for_topics(self, topic_ids: list[str]) -> list[TopicVoteRecord]:
        if not topic_ids:
            return []
        rows = self._session.scalars(
            select(TopicVoteModel)
            .where(TopicVoteModel.topic_id.in_(topic_ids))
            .order_by(TopicVoteModel.author_name),
        ).all()
        return [self._vote(row) for row in rows]

    def get_vote(self, topic_id: str, author_id: str) -> TopicVoteRecord | None:
        row = self._session.scalar(
            select(TopicVoteModel).where(
                TopicVoteModel.topic_id == topic_id,
                TopicVoteModel.author_id == author_id,
            ),
        )
        if row is None:
            return None
        return self._vote(row)

    def add_vote(self, vote: TopicVoteRecord) -> None:
        self._session.add(
            TopicVoteModel(
                id=vote.id,
                topic_id=vote.topic_id,
                author_id=vote.author_id,
                author_name=vote.author_name,
                choice=vote.choice,
            ),
        )

    def save_vote(self, vote: TopicVoteRecord) -> None:
        row = self._session.get(TopicVoteModel, vote.id)
        if row is not None:
            row.choice = vote.choice
            row.author_name = vote.author_name

    def list_opinions_for_topics(self, topic_ids: list[str]) -> list[TopicOpinionRecord]:
        if not topic_ids:
            return []
        rows = self._session.scalars(
            select(TopicOpinionModel)
            .where(TopicOpinionModel.topic_id.in_(topic_ids))
            .order_by(TopicOpinionModel.created_at),
        ).all()
        return [self._opinion(row) for row in rows]

    def get_opinion(self, topic_id: str, author_id: str) -> TopicOpinionRecord | None:
        row = self._session.scalar(
            select(TopicOpinionModel).where(
                TopicOpinionModel.topic_id == topic_id,
                TopicOpinionModel.author_id == author_id,
            ),
        )
        if row is None:
            return None
        return self._opinion(row)

    def add_opinion(self, opinion: TopicOpinionRecord) -> None:
        self._session.add(
            TopicOpinionModel(
                id=opinion.id,
                topic_id=opinion.topic_id,
                author_id=opinion.author_id,
                author_name=opinion.author_name,
                body=opinion.body,
                created_at=datetime.fromisoformat(opinion.created_at),
            ),
        )

    def save_opinion(self, opinion: TopicOpinionRecord) -> None:
        row = self._session.get(TopicOpinionModel, opinion.id)
        if row is not None:
            row.body = opinion.body
            row.author_name = opinion.author_name

    def list_attachments_for_topics(self, topic_ids: list[str]) -> list[TopicAttachmentRecord]:
        if not topic_ids:
            return []
        bind = self._session.get_bind()
        if bind is None or not inspect(bind).has_table("topic_attachments"):
            return []
        rows = self._session.scalars(
            select(TopicAttachmentModel)
            .where(TopicAttachmentModel.topic_id.in_(topic_ids))
            .order_by(TopicAttachmentModel.name),
        ).all()
        return [self._attachment(row) for row in rows]

    def replace_attachments(self, topic_id: str, attachments: list[TopicAttachmentRecord]) -> None:
        bind = self._session.get_bind()
        if bind is None or not inspect(bind).has_table("topic_attachments"):
            return
        self._session.execute(
            delete(TopicAttachmentModel).where(TopicAttachmentModel.topic_id == topic_id),
        )
        for attachment in attachments:
            self._session.add(
                TopicAttachmentModel(
                    id=attachment.id,
                    topic_id=attachment.topic_id,
                    kind=attachment.kind,
                    name=attachment.name,
                    url=attachment.url,
                ),
            )
        self._session.flush()

    def list_completion_attachments_for_topics(
        self,
        topic_ids: list[str],
    ) -> list[TopicAttachmentRecord]:
        if not topic_ids:
            return []
        bind = self._session.get_bind()
        if bind is None or not inspect(bind).has_table("topic_completion_attachments"):
            return []
        rows = self._session.scalars(
            select(TopicCompletionAttachmentModel)
            .where(TopicCompletionAttachmentModel.topic_id.in_(topic_ids))
            .order_by(TopicCompletionAttachmentModel.name),
        ).all()
        return [self._completion_attachment(row) for row in rows]

    def replace_completion_attachments(
        self,
        topic_id: str,
        attachments: list[TopicAttachmentRecord],
    ) -> None:
        bind = self._session.get_bind()
        if bind is None or not inspect(bind).has_table("topic_completion_attachments"):
            return
        self._session.execute(
            delete(TopicCompletionAttachmentModel).where(
                TopicCompletionAttachmentModel.topic_id == topic_id,
            ),
        )
        for attachment in attachments:
            self._session.add(
                TopicCompletionAttachmentModel(
                    id=attachment.id,
                    topic_id=attachment.topic_id,
                    kind=attachment.kind,
                    name=attachment.name,
                    url=attachment.url,
                ),
            )
        self._session.flush()

    def list_confirmations_for_topics(self, topic_ids: list[str]) -> list[TopicConfirmationRecord]:
        if not topic_ids:
            return []
        bind = self._session.get_bind()
        if bind is None or not inspect(bind).has_table("topic_confirmations"):
            return []
        rows = self._session.scalars(
            select(TopicConfirmationModel)
            .where(TopicConfirmationModel.topic_id.in_(topic_ids))
            .order_by(TopicConfirmationModel.created_at),
        ).all()
        return [self._confirmation(row) for row in rows]

    def get_confirmation(self, topic_id: str, author_id: str) -> TopicConfirmationRecord | None:
        bind = self._session.get_bind()
        if bind is None or not inspect(bind).has_table("topic_confirmations"):
            return None
        row = self._session.scalar(
            select(TopicConfirmationModel).where(
                TopicConfirmationModel.topic_id == topic_id,
                TopicConfirmationModel.author_id == author_id,
            ),
        )
        if row is None:
            return None
        return self._confirmation(row)

    def add_confirmation(self, confirmation: TopicConfirmationRecord) -> None:
        bind = self._session.get_bind()
        if bind is None or not inspect(bind).has_table("topic_confirmations"):
            return
        self._session.add(
            TopicConfirmationModel(
                id=confirmation.id,
                topic_id=confirmation.topic_id,
                author_id=confirmation.author_id,
                author_name=confirmation.author_name,
                created_at=datetime.fromisoformat(confirmation.created_at),
                choice=confirmation.choice or "yes",
                reason=confirmation.reason,
            ),
        )
        # Session uses autoflush=False; flush so majority checks see this vote.
        self._session.flush()

    def clear_confirmations_for_topic(self, topic_id: str) -> None:
        bind = self._session.get_bind()
        if bind is None or not inspect(bind).has_table("topic_confirmations"):
            return
        self._session.execute(
            delete(TopicConfirmationModel).where(TopicConfirmationModel.topic_id == topic_id),
        )
        self._session.flush()

    def _topic(self, row: TopicModel) -> TopicRecord:
        return TopicRecord(
            id=row.id,
            title=row.title,
            description=row.description,
            category_key=row.category_key,
            attachment_name=row.attachment_name,
            decision=row.decision,
            status_id=row.status_id,
            priority_id=row.priority_id,
            assignee_user_id=row.assignee_user_id,
            start_date=row.start_date.isoformat() if getattr(row, "start_date", None) else None,
            due_date=row.due_date.isoformat() if row.due_date else None,
            created_at=row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            closed_at=row.closed_at.isoformat() if getattr(row, "closed_at", None) else None,
            period_id=getattr(row, "period_id", None),
            completion_note=getattr(row, "completion_note", None),
            completion_submitted_at=(
                row.completion_submitted_at.isoformat()
                if getattr(row, "completion_submitted_at", None)
                else None
            ),
            completion_round=int(getattr(row, "completion_round", None) or 1),
            completion_rounds=self._parse_rounds(getattr(row, "completion_rounds_json", None)),
            vote_type=getattr(row, "vote_type", None) or VOTE_TYPE_YES_NO,
            vote_options=self._parse_options(getattr(row, "vote_options_json", None)),
            client_id=getattr(row, "client_id", None),
            voting_starts_at=_to_utc_iso(getattr(row, "voting_starts_at", None)),
            voting_ends_at=_to_utc_iso(getattr(row, "voting_ends_at", None)),
            status_entered_at=_to_utc_iso(getattr(row, "status_entered_at", None))
            or (row.created_at.isoformat() if getattr(row, "created_at", None) else None),
            deleted_at=_to_utc_iso(getattr(row, "deleted_at", None)),
        )

    def _options_json(self, options: tuple[TopicVoteOptionRecord, ...]) -> str:
        return json.dumps(
            [{"id": item.id, "label": item.label} for item in options],
            ensure_ascii=False,
        )

    def _rounds_json(self, rounds: tuple[TopicCompletionRoundRecord, ...]) -> str:
        """Serialize sealed rounds without large data-URL payloads (TEXT column limit)."""
        return json.dumps(
            [
                {
                    "roundNumber": item.round_number,
                    "note": item.note,
                    "submittedAt": item.submitted_at,
                    "closedAt": item.closed_at,
                    "outcome": item.outcome,
                    "confirmations": [
                        {
                            "id": vote.id,
                            "authorId": vote.author_id,
                            "authorName": vote.author_name,
                            "createdAt": vote.created_at,
                            "choice": vote.choice,
                            "reason": vote.reason,
                        }
                        for vote in item.confirmations
                    ],
                    "attachments": [
                        {
                            "id": file.id,
                            "topicId": file.topic_id,
                            "kind": file.kind,
                            "name": file.name,
                            # Keep only short http(s) URLs; skip base64 data URLs.
                            "url": file.url if self._is_compact_attachment_url(file.url) else "",
                        }
                        for file in item.attachments
                    ],
                }
                for item in rounds
            ],
            ensure_ascii=False,
        )

    @staticmethod
    def _is_compact_attachment_url(url: str) -> bool:
        cleaned = (url or "").strip()
        if not cleaned or cleaned.startswith("data:"):
            return False
        return len(cleaned) <= 2000

    def _parse_rounds(self, raw: str | None) -> tuple[TopicCompletionRoundRecord, ...]:
        if not raw:
            return ()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return ()
        if not isinstance(parsed, list):
            return ()
        rounds: list[TopicCompletionRoundRecord] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            try:
                round_number = int(item.get("roundNumber") or item.get("round_number") or 0)
            except (TypeError, ValueError):
                continue
            if round_number < 1:
                continue
            confirmations_raw = item.get("confirmations") or []
            attachments_raw = item.get("attachments") or []
            confirmations: list[TopicConfirmationRecord] = []
            if isinstance(confirmations_raw, list):
                for vote in confirmations_raw:
                    if not isinstance(vote, dict):
                        continue
                    confirmations.append(
                        TopicConfirmationRecord(
                            id=str(vote.get("id") or ""),
                            topic_id=str(vote.get("topicId") or vote.get("topic_id") or ""),
                            author_id=str(vote.get("authorId") or vote.get("author_id") or ""),
                            author_name=str(vote.get("authorName") or vote.get("author_name") or ""),
                            created_at=str(vote.get("createdAt") or vote.get("created_at") or ""),
                            choice=str(vote.get("choice") or "yes"),
                            reason=(str(vote["reason"]) if vote.get("reason") else None),
                        ),
                    )
            attachments: list[TopicAttachmentRecord] = []
            if isinstance(attachments_raw, list):
                for file in attachments_raw:
                    if not isinstance(file, dict):
                        continue
                    attachments.append(
                        TopicAttachmentRecord(
                            id=str(file.get("id") or ""),
                            topic_id=str(file.get("topicId") or file.get("topic_id") or ""),
                            kind=str(file.get("kind") or "file"),
                            name=str(file.get("name") or ""),
                            url=str(file.get("url") or ""),
                        ),
                    )
            rounds.append(
                TopicCompletionRoundRecord(
                    round_number=round_number,
                    note=str(item.get("note") or ""),
                    submitted_at=str(item.get("submittedAt") or item.get("submitted_at") or ""),
                    closed_at=str(item.get("closedAt") or item.get("closed_at") or ""),
                    outcome=str(item.get("outcome") or "failed"),
                    confirmations=tuple(confirmations),
                    attachments=tuple(attachments),
                ),
            )
        return tuple(rounds)

    def _parse_options(self, raw: str | None) -> tuple[TopicVoteOptionRecord, ...]:
        if not raw:
            return ()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return ()
        if not isinstance(parsed, list):
            return ()
        options: list[TopicVoteOptionRecord] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            option_id = str(item.get("id") or "").strip()
            label = str(item.get("label") or "").strip()
            if not option_id or not label:
                continue
            options.append(TopicVoteOptionRecord(id=option_id, label=label))
        return tuple(options)

    def _vote(self, row: TopicVoteModel) -> TopicVoteRecord:
        return TopicVoteRecord(
            id=row.id,
            topic_id=row.topic_id,
            author_id=row.author_id,
            author_name=row.author_name,
            choice=row.choice,
        )

    def _opinion(self, row: TopicOpinionModel) -> TopicOpinionRecord:
        return TopicOpinionRecord(
            id=row.id,
            topic_id=row.topic_id,
            author_id=row.author_id,
            author_name=row.author_name,
            body=row.body,
            created_at=row.created_at.isoformat(),
        )

    def _confirmation(self, row: TopicConfirmationModel) -> TopicConfirmationRecord:
        return TopicConfirmationRecord(
            id=row.id,
            topic_id=row.topic_id,
            author_id=row.author_id,
            author_name=row.author_name,
            created_at=row.created_at.isoformat(),
            choice=getattr(row, "choice", None) or "yes",
            reason=getattr(row, "reason", None),
        )

    def _attachment(self, row: TopicAttachmentModel) -> TopicAttachmentRecord:
        return TopicAttachmentRecord(
            id=row.id,
            topic_id=row.topic_id,
            kind=row.kind,
            name=row.name,
            url=row.url,
        )

    def _completion_attachment(self, row: TopicCompletionAttachmentModel) -> TopicAttachmentRecord:
        return TopicAttachmentRecord(
            id=row.id,
            topic_id=row.topic_id,
            kind=row.kind,
            name=row.name,
            url=row.url,
        )
