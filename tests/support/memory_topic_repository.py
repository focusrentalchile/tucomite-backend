"""In-memory topic repository for unit tests."""

from app.domain.topics import (
    StatusRecord,
    TopicAttachmentRecord,
    TopicConfirmationRecord,
    TopicOpinionRecord,
    TopicRecord,
    TopicVoteRecord,
)


class InMemoryTopicRepository:
    """Stores statuses, topics, votes, opinions, and attachments without MySQL."""

    def __init__(self) -> None:
        self.statuses: list[StatusRecord] = []
        self.topics: list[TopicRecord] = []
        self.votes: list[TopicVoteRecord] = []
        self.opinions: list[TopicOpinionRecord] = []
        self.attachments: list[TopicAttachmentRecord] = []
        self.completion_attachments: list[TopicAttachmentRecord] = []
        self.confirmations: list[TopicConfirmationRecord] = []

    def list_statuses(self) -> list[StatusRecord]:
        return sorted(self.statuses, key=lambda status: status.id)

    def add_status(self, status: StatusRecord) -> None:
        self.statuses.append(status)

    def save_status(self, status: StatusRecord) -> None:
        self.statuses = [status if item.id == status.id else item for item in self.statuses]

    def add_topic(self, topic: TopicRecord) -> None:
        self.topics.append(topic)

    def get_topic(self, topic_id: str) -> TopicRecord | None:
        return next((topic for topic in self.topics if topic.id == topic_id), None)

    def save_topic_status(self, topic_id: str, status_id: int) -> None:
        self.topics = [
            TopicRecord(
                id=topic.id,
                title=topic.title,
                description=topic.description,
                category_key=topic.category_key,
                attachment_name=topic.attachment_name,
                decision=topic.decision,
                status_id=status_id,
                priority_id=topic.priority_id,
                assignee_user_id=topic.assignee_user_id,
                start_date=topic.start_date,
                due_date=topic.due_date,
                created_at=topic.created_at,
                closed_at=topic.closed_at,
                period_id=topic.period_id,
                completion_note=topic.completion_note,
                completion_submitted_at=topic.completion_submitted_at,
            )
            if topic.id == topic_id
            else topic
            for topic in self.topics
        ]

    def save_topic(self, topic: TopicRecord) -> None:
        self.topics = [topic if item.id == topic.id else item for item in self.topics]

    def save_topic_completion(self, topic: TopicRecord) -> None:
        self.topics = [topic if item.id == topic.id else item for item in self.topics]

    def delete_topic(self, topic_id: str) -> None:
        self.votes = [vote for vote in self.votes if vote.topic_id != topic_id]
        self.opinions = [opinion for opinion in self.opinions if opinion.topic_id != topic_id]
        self.attachments = [item for item in self.attachments if item.topic_id != topic_id]
        self.completion_attachments = [
            item for item in self.completion_attachments if item.topic_id != topic_id
        ]
        self.confirmations = [item for item in self.confirmations if item.topic_id != topic_id]
        self.topics = [topic for topic in self.topics if topic.id != topic_id]

    def list_topics(self) -> list[TopicRecord]:
        return list(self.topics)

    def list_votes(self, topic_id: str) -> list[TopicVoteRecord]:
        return sorted(
            [vote for vote in self.votes if vote.topic_id == topic_id],
            key=lambda vote: vote.author_name,
        )

    def list_votes_for_topics(self, topic_ids: list[str]) -> list[TopicVoteRecord]:
        wanted = set(topic_ids)
        return sorted(
            [vote for vote in self.votes if vote.topic_id in wanted],
            key=lambda vote: vote.author_name,
        )

    def get_vote(self, topic_id: str, author_id: str) -> TopicVoteRecord | None:
        return next(
            (
                vote
                for vote in self.votes
                if vote.topic_id == topic_id and vote.author_id == author_id
            ),
            None,
        )

    def add_vote(self, vote: TopicVoteRecord) -> None:
        self.votes.append(vote)

    def save_vote(self, vote: TopicVoteRecord) -> None:
        self.votes = [vote if item.id == vote.id else item for item in self.votes]

    def list_opinions_for_topics(self, topic_ids: list[str]) -> list[TopicOpinionRecord]:
        wanted = set(topic_ids)
        return sorted(
            [opinion for opinion in self.opinions if opinion.topic_id in wanted],
            key=lambda opinion: opinion.created_at,
        )

    def get_opinion(self, topic_id: str, author_id: str) -> TopicOpinionRecord | None:
        return next(
            (
                opinion
                for opinion in self.opinions
                if opinion.topic_id == topic_id and opinion.author_id == author_id
            ),
            None,
        )

    def add_opinion(self, opinion: TopicOpinionRecord) -> None:
        self.opinions.append(opinion)

    def save_opinion(self, opinion: TopicOpinionRecord) -> None:
        self.opinions = [opinion if item.id == opinion.id else item for item in self.opinions]

    def list_attachments_for_topics(self, topic_ids: list[str]) -> list[TopicAttachmentRecord]:
        wanted = set(topic_ids)
        return sorted(
            [item for item in self.attachments if item.topic_id in wanted],
            key=lambda item: item.name,
        )

    def replace_attachments(self, topic_id: str, attachments: list[TopicAttachmentRecord]) -> None:
        self.attachments = [item for item in self.attachments if item.topic_id != topic_id]
        self.attachments.extend(attachments)

    def list_completion_attachments_for_topics(
        self,
        topic_ids: list[str],
    ) -> list[TopicAttachmentRecord]:
        wanted = set(topic_ids)
        return sorted(
            [item for item in self.completion_attachments if item.topic_id in wanted],
            key=lambda item: item.name,
        )

    def replace_completion_attachments(
        self,
        topic_id: str,
        attachments: list[TopicAttachmentRecord],
    ) -> None:
        self.completion_attachments = [
            item for item in self.completion_attachments if item.topic_id != topic_id
        ]
        self.completion_attachments.extend(attachments)

    def list_confirmations_for_topics(self, topic_ids: list[str]) -> list[TopicConfirmationRecord]:
        wanted = set(topic_ids)
        return sorted(
            [item for item in self.confirmations if item.topic_id in wanted],
            key=lambda item: item.created_at,
        )

    def get_confirmation(self, topic_id: str, author_id: str) -> TopicConfirmationRecord | None:
        return next(
            (
                item
                for item in self.confirmations
                if item.topic_id == topic_id and item.author_id == author_id
            ),
            None,
        )

    def add_confirmation(self, confirmation: TopicConfirmationRecord) -> None:
        self.confirmations.append(confirmation)
