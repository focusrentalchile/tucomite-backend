"""Request-scoped dependencies for persistence and the signed-in actor."""

from typing import NamedTuple

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.access_catalog import access_catalog
from app.core.database import get_db
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.repositories.committee_repository import SqlCommitteeRepository
from app.repositories.period_repository import SqlPeriodRepository
from app.repositories.project_repository import SqlProjectRepository
from app.repositories.topic_repository import SqlTopicRepository
from app.services.access_service import PermissionPolicy, RoleService, UserService
from app.services.client_service import ClientService
from app.services.committee_access import ensure_committee_access
from app.services.committee_service import CommitteeService
from app.services.period_service import PeriodService
from app.services.project_service import ProjectService
from app.services.report_service import ReportService
from app.services.topic_service import TopicService

SESSION_USER_KEY = "user_id"


class Actor(NamedTuple):
    """The person performing the request."""

    user_id: str
    permissions: frozenset[str]
    is_super_admin: bool
    client_id: str | None


def get_role_service(db: Session = Depends(get_db)) -> RoleService:
    """Build a role service bound to the request session."""
    return RoleService(SqlAccessRepository(db), access_catalog)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Build a user service bound to the request session."""
    return UserService(SqlAccessRepository(db))


def get_client_service(db: Session = Depends(get_db)) -> ClientService:
    """Build a client service bound to the request session."""
    return ClientService(SqlClientRepository(db), SqlAccessRepository(db))


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


def get_current_actor(request: Request, db: Session = Depends(get_db)) -> Actor:
    """Resolve the signed-in user from the session cookie."""
    user_id = request.session.get(SESSION_USER_KEY)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    repository = SqlAccessRepository(db)
    user = repository.get_user(str(user_id))
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Authentication required.")
    role = repository.get_role(user.role_id)
    if role is None:
        raise HTTPException(status_code=503, detail="Role is not available.")
    return Actor(
        user_id=user.id,
        permissions=role.permissions,
        is_super_admin=role.system,
        client_id=user.client_id,
    )


def require_permission(module_key: str, functionality_key: str):
    """Depend on an actor who holds one catalog permission."""

    def dependency(actor: Actor = Depends(get_current_actor)) -> Actor:
        if not PermissionPolicy().allows(actor.permissions, module_key, functionality_key):
            raise HTTPException(status_code=403, detail="Forbidden.")
        return actor

    return dependency


def require_super_admin(actor: Actor = Depends(get_current_actor)) -> Actor:
    """Depend on the platform super admin."""
    if not actor.is_super_admin:
        raise HTTPException(status_code=403, detail="Forbidden.")
    return actor


def require_committee_member(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> Actor:
    """Depend on an actor who may act with committee powers."""
    repository = SqlAccessRepository(db)
    user = repository.get_user(actor.user_id)
    role = repository.get_role(user.role_id) if user is not None else None
    role_name = role.name if role is not None else ""
    if not ensure_committee_access(db, actor.user_id, role_name, actor.permissions):
        raise HTTPException(status_code=403, detail="Committee membership required.")
    return actor


def require_period_access(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> Actor:
    """Settings managers (users/roles) or committee members may use periods."""
    if "users.view" in actor.permissions or "roles.view" in actor.permissions:
        return actor
    return require_committee_member(actor, db)
