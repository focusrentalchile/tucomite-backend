"""Delete every row that still blocks removing a platform client."""

from sqlalchemy import delete, or_, select, text
from sqlalchemy.orm import Session

from app.models.access import UserModel
from app.models.account import AccountClosureRequestModel
from app.models.agreements import AgreementModel
from app.models.building_wall import BuildingWallPostModel
from app.models.client_settings import ClientSettingsModel
from app.models.committee import CommitteeMemberModel
from app.models.invitations import InvitationModel
from app.models.legal import LegalCaseAttachmentModel, LegalCaseMessageModel, LegalCaseModel
from app.models.management import (
    ManagementAttachmentModel,
    ManagementMessageModel,
    ManagementTaskModel,
    ManagementWorkspaceImportModel,
)
from app.models.messages import (
    ResidentMessageAttachmentModel,
    ResidentMessageModel,
    ResidentMessageParticipantModel,
    ResidentMessageReplyModel,
    ResidentMessageStatusEventModel,
)
from app.models.notifications import NotificationModel
from app.models.periods import PeriodModel
from app.models.projects import ProjectAttachmentModel, ProjectModel
from app.models.support import SupportAttachmentModel, SupportReplyModel, SupportTicketModel
from app.models.topics import (
    TopicAttachmentModel,
    TopicCompletionAttachmentModel,
    TopicConfirmationModel,
    TopicModel,
    TopicOpinionModel,
    TopicVoteModel,
)


def _purge_topics(session: Session, topic_ids: list[str]) -> None:
    """Remove topics and every row that still points at them."""
    if not topic_ids:
        return
    session.execute(delete(AgreementModel).where(AgreementModel.topic_id.in_(topic_ids)))
    session.execute(delete(TopicVoteModel).where(TopicVoteModel.topic_id.in_(topic_ids)))
    session.execute(delete(TopicOpinionModel).where(TopicOpinionModel.topic_id.in_(topic_ids)))
    session.execute(
        delete(TopicConfirmationModel).where(TopicConfirmationModel.topic_id.in_(topic_ids)),
    )
    session.execute(
        delete(TopicAttachmentModel).where(TopicAttachmentModel.topic_id.in_(topic_ids)),
    )
    session.execute(
        delete(TopicCompletionAttachmentModel).where(
            TopicCompletionAttachmentModel.topic_id.in_(topic_ids),
        ),
    )
    session.execute(delete(TopicModel).where(TopicModel.id.in_(topic_ids)))


def _purge_legacy_gestion_tables(session: Session, client_id: str, user_ids: list[str]) -> None:
    """Remove leftover rows from renamed gestion_* tables that still keep MySQL FKs."""
    from sqlalchemy import bindparam

    session.execute(
        text("DELETE FROM gestion_workspace_imports WHERE client_id = :client_id"),
        {"client_id": client_id},
    )
    session.execute(
        text("DELETE FROM gestion_tasks WHERE client_id = :client_id"),
        {"client_id": client_id},
    )
    if not user_ids:
        return
    user_ids_param = bindparam("user_ids", expanding=True)
    session.execute(
        text(
            "DELETE FROM gestion_workspace_imports WHERE administrator_user_id IN :user_ids"
        ).bindparams(user_ids_param),
        {"user_ids": user_ids},
    )
    session.execute(
        text(
            """
            DELETE gm FROM gestion_messages gm
            INNER JOIN gestion_tasks gt ON gt.id = gm.task_id
            WHERE gt.created_by_user_id IN :user_ids
               OR gt.assignee_user_id IN :user_ids
               OR gm.author_user_id IN :user_ids
            """
        ).bindparams(user_ids_param),
        {"user_ids": user_ids},
    )
    session.execute(
        text(
            """
            DELETE FROM gestion_tasks
            WHERE created_by_user_id IN :user_ids
               OR assignee_user_id IN :user_ids
            """
        ).bindparams(user_ids_param),
        {"user_ids": user_ids},
    )


def purge_client_dependencies(session: Session, client_id: str) -> None:
    """Remove building-scoped rows so the client (and its users) can be deleted."""
    user_ids = list(
        session.scalars(select(UserModel.id).where(UserModel.client_id == client_id)).all(),
    )
    if user_ids:
        session.execute(
            delete(CommitteeMemberModel).where(CommitteeMemberModel.user_id.in_(user_ids)),
        )
        session.execute(delete(NotificationModel).where(NotificationModel.user_id.in_(user_ids)))
        session.execute(
            delete(InvitationModel).where(InvitationModel.invited_by_user_id.in_(user_ids)),
        )

    _purge_legacy_gestion_tables(session, client_id, user_ids)

    period_ids = list(
        session.scalars(select(PeriodModel.id).where(PeriodModel.client_id == client_id)).all(),
    )
    topic_filters = [TopicModel.client_id == client_id]
    if period_ids:
        topic_filters.append(TopicModel.period_id.in_(period_ids))
    topic_ids = list(session.scalars(select(TopicModel.id).where(or_(*topic_filters))).all())
    _purge_topics(session, topic_ids)

    session.execute(delete(AgreementModel).where(AgreementModel.client_id == client_id))

    if period_ids:
        project_ids = list(
            session.scalars(select(ProjectModel.id).where(ProjectModel.period_id.in_(period_ids))).all(),
        )
        if project_ids:
            session.execute(
                delete(ProjectAttachmentModel).where(ProjectAttachmentModel.project_id.in_(project_ids)),
            )
            session.execute(delete(ProjectModel).where(ProjectModel.id.in_(project_ids)))
        session.execute(delete(PeriodModel).where(PeriodModel.id.in_(period_ids)))

    case_ids = list(
        session.scalars(select(LegalCaseModel.id).where(LegalCaseModel.client_id == client_id)).all(),
    )
    if case_ids:
        session.execute(
            delete(LegalCaseAttachmentModel).where(LegalCaseAttachmentModel.case_id.in_(case_ids)),
        )
        session.execute(
            delete(LegalCaseMessageModel).where(LegalCaseMessageModel.case_id.in_(case_ids)),
        )
        session.execute(delete(LegalCaseModel).where(LegalCaseModel.id.in_(case_ids)))

    message_ids = list(
        session.scalars(
            select(ResidentMessageModel.id).where(ResidentMessageModel.client_id == client_id),
        ).all(),
    )
    if message_ids:
        reply_ids = list(
            session.scalars(
                select(ResidentMessageReplyModel.id).where(
                    ResidentMessageReplyModel.message_id.in_(message_ids),
                ),
            ).all(),
        )
        if reply_ids:
            session.execute(
                delete(ResidentMessageAttachmentModel).where(
                    ResidentMessageAttachmentModel.reply_id.in_(reply_ids),
                ),
            )
        session.execute(
            delete(ResidentMessageAttachmentModel).where(
                ResidentMessageAttachmentModel.message_id.in_(message_ids),
            ),
        )
        session.execute(
            delete(ResidentMessageReplyModel).where(
                ResidentMessageReplyModel.message_id.in_(message_ids),
            ),
        )
        session.execute(
            delete(ResidentMessageStatusEventModel).where(
                ResidentMessageStatusEventModel.message_id.in_(message_ids),
            ),
        )
        session.execute(
            delete(ResidentMessageParticipantModel).where(
                ResidentMessageParticipantModel.message_id.in_(message_ids),
            ),
        )
        session.execute(delete(ResidentMessageModel).where(ResidentMessageModel.id.in_(message_ids)))

    task_ids = list(
        session.scalars(
            select(ManagementTaskModel.id).where(ManagementTaskModel.client_id == client_id),
        ).all(),
    )
    if task_ids:
        session.execute(
            delete(ManagementAttachmentModel).where(ManagementAttachmentModel.task_id.in_(task_ids)),
        )
        session.execute(
            delete(ManagementMessageModel).where(ManagementMessageModel.task_id.in_(task_ids)),
        )
        session.execute(delete(ManagementTaskModel).where(ManagementTaskModel.id.in_(task_ids)))

    session.execute(
        delete(ManagementWorkspaceImportModel).where(
            ManagementWorkspaceImportModel.client_id == client_id,
        ),
    )
    session.execute(delete(BuildingWallPostModel).where(BuildingWallPostModel.client_id == client_id))
    session.execute(delete(ClientSettingsModel).where(ClientSettingsModel.client_id == client_id))
    session.execute(
        delete(AccountClosureRequestModel).where(AccountClosureRequestModel.client_id == client_id),
    )
    session.execute(delete(InvitationModel).where(InvitationModel.client_id == client_id))

    ticket_ids = list(
        session.scalars(
            select(SupportTicketModel.id).where(SupportTicketModel.client_id == client_id),
        ).all(),
    )
    if ticket_ids:
        session.execute(
            delete(SupportAttachmentModel).where(SupportAttachmentModel.ticket_id.in_(ticket_ids)),
        )
        session.execute(delete(SupportReplyModel).where(SupportReplyModel.ticket_id.in_(ticket_ids)))
        session.execute(delete(SupportTicketModel).where(SupportTicketModel.id.in_(ticket_ids)))

    session.flush()
