"""Router aggregation target for the backend refactor.

Routers are intentionally not wired into ``backend.app.main`` yet. The live app
is still exported from root ``main.py`` while endpoint groups are migrated.
"""

from fastapi import APIRouter

from backend.app.api.v1.endpoints import (
    chat,
    health,
    internal,
    market,
    payments,
    platform,
    providers,
    reports,
    wallets,
)

api_router = APIRouter()

for router in (
    health.router,
    providers.router,
    wallets.router,
    platform.router,
    market.router,
    payments.router,
    internal.router,
    reports.router,
    chat.router,
):
    api_router.include_router(router)

__all__ = ["api_router"]
