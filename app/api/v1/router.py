"""Aggregates every v1 endpoint router."""

from fastapi import APIRouter

from app.api.v1.endpoints import access, auth, clients, committee, health, periods, projects, reports, support, topics

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(access.router)
api_router.include_router(clients.router)
api_router.include_router(committee.router)
api_router.include_router(periods.router)
api_router.include_router(projects.router)
api_router.include_router(reports.router)
api_router.include_router(support.router)
api_router.include_router(topics.router)
