"""Request-scoped dependencies for persistence and the acting super admin."""

from typing import NamedTuple

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.access_catalog import access_catalog
from app.core.database import get_db
from app.domain.access import SUPER_ADMIN_EMAIL
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.committee_repository import SqlCommitteeRepository
from app.repositories.period_repository import SqlPeriodRepository
from app.repositories.project_repository import SqlProjectRepository
from app.repositories.topic_repository import SqlTopicRepository
from app.services.access_service import PermissionPolicy, RoleService, UserService
from app.services.committee_service import CommitteeService
from app.services.period_service import PeriodService
from app.services.project_service import ProjectService
from app.services.report_service import ReportService
from app.services.topic_service import TopicService


class Actor(NamedTuple):
    """The person performing the request."""

    user_id: str
    permissions: frozenset[str]


def get_role_service(db: Session = Depends(get_db)) -> RoleService:
    """Build a role service bound to the request session."""
    return RoleService(SqlAccessRepository(db), access_catalog)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Build a user service bound to the request session."""
    return UserService(SqlAccessRepository(db))


def get_topic_service(db: Session = Depends(get_db)) -> TopicService:
    """Build a topic service bound to the request session."""
    return TopicService(SqlTopicRepository(db))


def get_committee_service(db: Session = Depends(get_db)) -> CommitteeService:
    """Build a committee service bound to the request session."""
    return CommitteeService(SqlCommitteeRepository(db))


def get_period_service(db: Session = Depends(get_db)) -> PeriodService:
    """Build a period service bound to the request session."""
    return PeriodService(SqlPeriodRepository(db))


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    """Build a project service bound to the request session."""
    return ProjectService(SqlProjectRepository(db), SqlPeriodRepository(db))


def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    """Build a report service bound to the request session."""
    return ReportService(SqlTopicRepository(db), SqlProjectRepository(db), SqlPeriodRepository(db))


def get_current_actor(db: Session = Depends(get_db)) -> Actor:
    """Resolve the seeded super admin until sign-in selects the actor."""
    repository = SqlAccessRepository(db)
    user = repository.get_user_by_email(SUPER_ADMIN_EMAIL)
    if user is None:
        raise HTTPException(status_code=503, detail="Super admin is not available.")
    role = repository.get_role(user.role_id)
    if role is None:
        raise HTTPException(status_code=503, detail="Super admin is not available.")
    return Actor(user_id=user.id, permissions=role.permissions)


def require_permission(module_key: str, functionality_key: str):
    """Depend on an actor who holds one catalog permission."""

    def dependency(actor: Actor = Depends(get_current_actor)) -> Actor:
        if not PermissionPolicy().allows(actor.permissions, module_key, functionality_key):
            raise HTTPException(status_code=403, detail="Forbidden.")
        return actor

    return dependency


def require_committee_member(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> Actor:
    """Depend on an actor who belongs to the building committee."""
    if SqlCommitteeRepository(db).get_member(actor.user_id) is None:
        raise HTTPException(status_code=403, detail="Committee membership required.")
    return actor
