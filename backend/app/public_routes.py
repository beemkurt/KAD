from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.public_subscription import (
    PublicSubscriptionNotFound,
    PublicSubscriptionUpstreamError,
    fetch_public_subscription,
)


router = APIRouter()


@router.get(
    "/{token}",
    include_in_schema=False,
)
async def public_subscription(
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
