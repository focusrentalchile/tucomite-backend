"""Seeds the status table, creates topics, and stores votes."""



import uuid



from app.domain.topics import (

    MEDIUM_PRIORITY_ID,

    OPEN_STATUS_ID,

    PRIORITY_IDS,

    VOTE_CHOICES,

    WAITING_STATUS_ID,

    InvalidTopicPriority,

    InvalidTopicStatus,

    InvalidVoteChoice,

    StatusRecord,

    TopicNotFound,

    TopicRecord,

    TopicVoteRecord,

    TOPIC_PRIORITIES,

    TOPIC_STATUSES,

    VoteAlreadyCast,

)

_VALID_STATUS_IDS = {status_id for status_id, _ in TOPIC_STATUSES}

from app.repositories.topic_repository import TopicRepository





def ensure_topic_statuses(repository: TopicRepository) -> None:

    """Insert the four board statuses with their stable ids."""

    stored = {status.id: status for status in repository.list_statuses()}

    for status_id, key in TOPIC_STATUSES:

        current = stored.get(status_id)

        if current is None:

            repository.add_status(StatusRecord(id=status_id, key=key))

        elif current.key != key:

            repository.save_status(StatusRecord(id=status_id, key=key))


def ensure_topic_priorities(session) -> None:
    """Insert the three priority rows with their stable ids."""
    from app.models.topics import PriorityModel

    for priority_id, key in TOPIC_PRIORITIES:
        current = session.get(PriorityModel, priority_id)
        if current is None:
            session.add(PriorityModel(id=priority_id, key=key))
        elif current.key != key:
            current.key = key


class TopicService:

    """Creates topics and records yes, no, or abstain votes in MySQL."""



    def __init__(self, repository: TopicRepository) -> None:

        self._repository = repository



    def list_topics(self) -> list[TopicRecord]:

        """Return every stored topic."""

        return self._repository.list_topics()



    def list_votes_for_topics(self, topic_ids: list[str]) -> list[TopicVoteRecord]:

        """Return every vote for the given topics."""

        return self._repository.list_votes_for_topics(topic_ids)



    def create_topic(

        self,

        title: str,

        description: str,

        category_key: str,

        attachment_name: str,

        decision: str,

        priority_id: int = MEDIUM_PRIORITY_ID,

        period_id: str | None = None,

    ) -> TopicRecord:

        """Store a topic in the open status."""

        if priority_id not in PRIORITY_IDS:

            raise InvalidTopicPriority()

        topic = TopicRecord(

            id=str(uuid.uuid4()),

            title=title.strip(),

            description=description.strip(),

            category_key=category_key.strip(),

            attachment_name=attachment_name.strip(),

            decision=decision.strip(),

            status_id=OPEN_STATUS_ID,

            priority_id=priority_id,

            period_id=period_id,

        )

        self._repository.add_topic(topic)

        return topic



    def update_topic(

        self,

        topic_id: str,

        title: str,

        description: str,

        category_key: str,

        attachment_name: str,

        decision: str,

        priority_id: int = MEDIUM_PRIORITY_ID,

    ) -> TopicRecord:

        """Update the editable fields of one topic."""

        if priority_id not in PRIORITY_IDS:

            raise InvalidTopicPriority()

        current = self._repository.get_topic(topic_id)

        if current is None:

            raise TopicNotFound()

        topic = TopicRecord(

            id=current.id,

            title=title.strip(),

            description=description.strip(),

            category_key=category_key.strip(),

            attachment_name=attachment_name.strip(),

            decision=decision.strip(),

            status_id=current.status_id,

            priority_id=priority_id,

        )

        self._repository.save_topic(topic)

        return topic



    def move_topic(self, topic_id: str, status_id: int) -> TopicRecord:

        """Move one topic to another board column."""

        if status_id not in _VALID_STATUS_IDS:

            raise InvalidTopicStatus()

        current = self._repository.get_topic(topic_id)

        if current is None:

            raise TopicNotFound()

        self._repository.save_topic_status(topic_id, status_id)

        return TopicRecord(

            id=current.id,

            title=current.title,

            description=current.description,

            category_key=current.category_key,

            attachment_name=current.attachment_name,

            decision=current.decision,

            status_id=status_id,

            priority_id=current.priority_id,

        )



    def delete_topic(self, topic_id: str) -> None:

        """Remove one topic and its votes."""

        if self._repository.get_topic(topic_id) is None:

            raise TopicNotFound()

        self._repository.delete_topic(topic_id)



    def cast_vote(

        self,

        topic_id: str,

        author_id: str,

        author_name: str,

        choice: str,

    ) -> tuple[TopicRecord, TopicVoteRecord]:

        """Store one person's first vote and move the topic to waiting."""

        normalized = choice.strip().lower()

        if normalized not in VOTE_CHOICES:

            raise InvalidVoteChoice()



        topic = self._repository.get_topic(topic_id)

        if topic is None:

            raise TopicNotFound()



        existing = self._repository.get_vote(topic_id, author_id)

        if existing is not None:

            raise VoteAlreadyCast()



        vote = TopicVoteRecord(

            id=str(uuid.uuid4()),

            topic_id=topic_id,

            author_id=author_id,

            author_name=author_name.strip(),

            choice=normalized,

        )

        self._repository.add_vote(vote)



        if topic.status_id == OPEN_STATUS_ID:

            self._repository.save_topic_status(topic_id, WAITING_STATUS_ID)

            topic = TopicRecord(

                id=topic.id,

                title=topic.title,

                description=topic.description,

                category_key=topic.category_key,

                attachment_name=topic.attachment_name,

                decision=topic.decision,

                status_id=WAITING_STATUS_ID,

                priority_id=topic.priority_id,

            )



        return topic, vote

