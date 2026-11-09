"""SQLAlchemy models."""

from app.models.access import FunctionalityModel, ModuleModel, RoleModel, RolePermissionModel, UserModel
from app.models.agreements import AgreementModel
from app.models.blog import BlogPostModel
from app.models.contact import ContactMessageModel
from app.models.committee import CommitteeMemberModel
from app.models.legal import LegalCaseAttachmentModel, LegalCaseModel
from app.models.management import ManagementMessageModel, ManagementTaskModel, ManagementWorkspaceImportModel
from app.models.notifications import NotificationModel
from app.models.periods import PeriodModel
from app.models.projects import ProjectAttachmentModel, ProjectModel
from app.models.support import SupportReplyModel, SupportTicketModel, SupportTypeModel
from app.models.topics import (
    PriorityModel,
    StatusModel,
    TopicAttachmentModel,
    TopicModel,
    TopicOpinionModel,
    TopicVoteModel,
)

__all__ = [
    "AgreementModel",
    "BlogPostModel",
    "ContactMessageModel",
    "CommitteeMemberModel",
    "FunctionalityModel",
    "LegalCaseAttachmentModel",
    "LegalCaseModel",
    "ManagementMessageModel",
    "ManagementTaskModel",
    "ManagementWorkspaceImportModel",
    "ModuleModel",
    "NotificationModel",
    "PeriodModel",
    "PriorityModel",
    "ProjectAttachmentModel",
    "ProjectModel",
    "RoleModel",
    "RolePermissionModel",
    "StatusModel",
    "SupportReplyModel",
    "SupportTicketModel",
    "SupportTypeModel",
    "TopicAttachmentModel",
    "TopicModel",
    "TopicOpinionModel",
    "TopicVoteModel",
    "UserModel",
]
