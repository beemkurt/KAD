from contextlib import asynccontextmanager
from hmac import compare_digest

from fastapi import Depends, FastAPI, HTTPException, Request

from app.config import get_settings
from app.db import get_health, init_db
from app.plans import get_public_plans
from app.profiles import get_or_create_profile
from app.orders import (
    OrderError,
    create_order,
    get_current_order,
)
from app.connection_tokens import (
    ConnectionUnavailable,
    get_or_create_connection,
)
from app.provisioning import (
    ProvisioningError,
    ProvisioningService,
)
from app.schemas import (
    CreateOrderRequest,
    TestProvisionRequest,
)
from app.xui import XUIClient, XUIError
from app.telegram_auth import (
    TelegramMiniAppUser,
    require_telegram_user,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="KAD VPN Backend",
    version="0.11.0",
    docs_url="/docs",
    lifespan=lifespan,
)

from fastapi.responses import JSONResponse, Response

from app.public_subscription import (
    PublicSubscriptionNotFound,
    PublicSubscriptionUpstreamError,
    fetch_public_subscription,
)

settings = get_settings()
xui = XUIClient(settings)

provisioning = ProvisioningService(
    settings,
    xui,
)



@app.middleware("http")
async def protect_internal(request: Request, call_next):
    path = request.url.path

    if path == "/internal" or path.startswith("/internal/"):
        configured = settings.internal_api_token
        provided = request.headers.get("X-KAD-Internal-Token")

        if (
            configured is None
            or not provided
            or not compare_digest(
                provided,
                configured.get_secret_value()
            )
        ):
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"}
            )

    return await call_next(request)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "kad-vpn-backend",
        "version": "0.11.0",
    }


@app.get("/api/v1/auth/check")
async def auth_check(
    user: TelegramMiniAppUser = Depends(
        require_telegram_user
    ),
) -> dict[str, object]:
    return {
        "status": "ok",
        "authenticated": True,
        "user": {
            "telegram_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "language_code": user.language_code,
            "is_admin": (
                user.id
                == settings.telegram_admin_id
            ),
        },
    }


@app.get("/api/v1/me")
async def current_user_profile(
    user: TelegramMiniAppUser = Depends(
        require_telegram_user
    ),
) -> dict[str, object]:
    profile = get_or_create_profile(
        user,
        admin_id=settings.telegram_admin_id,
    )

    return {
        "status": "ok",
        **profile,
    }


@app.get("/api/v1/connection")
async def current_user_connection(
    user: TelegramMiniAppUser = Depends(
        require_telegram_user
    ),
) -> dict[str, object]:
    get_or_create_profile(
        user,
        admin_id=settings.telegram_admin_id,
    )

    try:
        connection = get_or_create_connection(
            user.id
        )

    except ConnectionUnavailable as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "code": exc.code,
                "message": str(exc),
            },
        ) from exc

    return {
        "status": "ok",
        "connection": connection,
    }


@app.get("/api/v1/plans")
async def public_plans() -> dict[str, object]:
    return {
        "status": "ok",
        "plans": get_public_plans(),
    }



@app.post("/api/v1/orders")
async def create_current_user_order(
    request: CreateOrderRequest,
    user: TelegramMiniAppUser = Depends(
        require_telegram_user
    ),
) -> dict[str, object]:
    get_or_create_profile(
        user,
        admin_id=settings.telegram_admin_id,
    )

    try:
        order, created = create_order(
            user.id,
            request.plan_code,
        )

    except OrderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": str(exc),
            },
        ) from exc

    return {
        "status": "ok",
        "created": created,
        "order": order,
    }


@app.get("/api/v1/orders/current")
async def current_user_order(
    user: TelegramMiniAppUser = Depends(
        require_telegram_user
    ),
) -> dict[str, object]:
    get_or_create_profile(
        user,
        admin_id=settings.telegram_admin_id,
    )

    return {
        "status": "ok",
        "order": get_current_order(
            user.id
        ),
    }


@app.get("/internal/db/health")
async def db_health() -> dict[str, object]:
    return get_health()


@app.get("/internal/xui/health")
async def xui_health() -> dict[str, object]:
    try:
        inbound = await xui.get_inbound(
            settings.xui_inbound_id
        )
    except XUIError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return {
        "status": "ok",
        "xui": {
            "reachable": True,
            "inbound_id": inbound.get("id"),
            "remark": inbound.get("remark"),
            "protocol": inbound.get("protocol"),
            "port": inbound.get("port"),
            "enabled": inbound.get("enable"),
        },
    }


@app.post("/internal/test/provision")
async def provision_test(
    request: TestProvisionRequest,
) -> dict[str, object]:
    try:
        return await provisioning.provision_test_client(
            telegram_id=request.telegram_id,
            duration_minutes=request.duration_minutes,
        )
    except (XUIError, ProvisioningError) as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@app.get("/internal/test/state/{telegram_id}")
async def test_state(
    telegram_id: int,
) -> dict[str, object]:
    state = provisioning.get_state(
        telegram_id
    )

    if state is None:
        raise HTTPException(
            status_code=404,
            detail="Пользователь не найден",
        )

    return state


@app.delete("/internal/test/purge/{telegram_id}")
async def purge_test(
    telegram_id: int,
) -> dict[str, object]:
    try:
        deleted = await provisioning.purge_test_client(
            telegram_id
        )
    except XUIError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Пользователь не найден",
        )

    return {
        "status": "ok",
        "deleted": True,
    }

@app.get(
    "/{token}",
    include_in_schema=False,
)
async def public_subscription_route(
    token: str,
) -> Response:
    try:
        content, headers = (
            await fetch_public_subscription(
                token
            )
        )

    except PublicSubscriptionNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Not found",
        ) from exc

    except PublicSubscriptionUpstreamError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Subscription service unavailable"
            ),
        ) from exc

    return Response(
        content=content,
        status_code=200,
        headers=headers,
    )
