"""In-memory topic repository for unit tests."""



from app.domain.topics import StatusRecord, TopicRecord, TopicVoteRecord





class InMemoryTopicRepository:

    """Stores statuses, topics, and votes without MySQL."""



    def __init__(self) -> None:

        self.statuses: list[StatusRecord] = []

        self.topics: list[TopicRecord] = []

        self.votes: list[TopicVoteRecord] = []



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

            )

            if topic.id == topic_id

            else topic

            for topic in self.topics

        ]



    def save_topic(self, topic: TopicRecord) -> None:

        self.topics = [topic if item.id == topic.id else item for item in self.topics]



    def delete_topic(self, topic_id: str) -> None:

        self.votes = [vote for vote in self.votes if vote.topic_id != topic_id]

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

