"""SQLAlchemy models."""

from app.models.access import FunctionalityModel, ModuleModel, RoleModel, RolePermissionModel, UserModel
from app.models.agreements import AgreementModel
from app.models.blog import BlogPostModel
from app.models.building_wall import BuildingWallPostModel
from app.models.contact import ContactMessageModel
from app.models.committee import CommitteeMemberModel
from app.models.legal import LegalCaseAttachmentModel, LegalCaseModel
from app.models.account import AccountClosureRequestModel
from app.models.client_settings import ClientSettingsModel
from app.models.management import (
    ManagementAttachmentModel,
    ManagementMessageModel,
    ManagementTaskModel,
    ManagementWorkspaceImportModel,
)
from app.models.notifications import NotificationModel
from app.models.periods import PeriodModel
from app.models.platform_settings import PlatformSettingsModel
from app.models.projects import ProjectAttachmentModel, ProjectModel
from app.models.support import (
    SupportAttachmentModel,
    SupportReplyModel,
    SupportTicketModel,
    SupportTypeModel,
)
from app.models.topics import (
    PriorityModel,
    StatusModel,
    TopicAttachmentModel,
    TopicModel,
    TopicOpinionModel,
    TopicVoteModel,
)

__all__ = [
    "AccountClosureRequestModel",
    "AgreementModel",
    "ClientSettingsModel",
    "ManagementAttachmentModel",
    "BlogPostModel",
    "BuildingWallPostModel",
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
    "PlatformSettingsModel",
    "PriorityModel",
    "ProjectAttachmentModel",
    "ProjectModel",
    "RoleModel",
    "RolePermissionModel",
    "StatusModel",
    "SupportAttachmentModel",
    "SupportReplyModel",
    "SupportTicketModel",
    "SupportTypeModel",
    "TopicAttachmentModel",
    "TopicModel",
    "TopicOpinionModel",
    "TopicVoteModel",
    "UserModel",
]
