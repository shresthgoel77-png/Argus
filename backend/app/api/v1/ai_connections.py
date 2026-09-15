from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.integrations.ai.exceptions import (
    AIProviderRateLimitedError,
    AIProviderUnavailableError,
    InvalidAPIKeyError,
    UnknownProviderError,
)
from app.models.user import User
from app.schemas.ai_connection import (
    AIConnectionCreate,
    AIConnectionNotConfigured,
    AIConnectionStatus,
)
from app.services import ai_connection_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/connection",
    response_model=AIConnectionStatus,
    status_code=status.HTTP_201_CREATED,
)
def create_connection(
    connection_in: AIConnectionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIConnectionStatus:
    try:
        ai_connection_service.create_or_replace_connection(
            db=db,
            user_id=user.id,
            provider_key=connection_in.provider,
            model=connection_in.model,
            api_key=connection_in.api_key,
        )
    except InvalidAPIKeyError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The provided API key could not be validated.",
        )
    except AIProviderRateLimitedError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The AI provider is rate limited. Please try again later.",
        )
    except AIProviderUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI provider is currently unavailable. Please try again later.",
        )
    except (UnknownProviderError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected AI provider or model is not supported.",
        )

    connection_status = ai_connection_service.get_connection_status(db, user.id)
    if connection_status is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The AI connection could not be loaded after saving.",
        )
    return {"configured": True, **connection_status}


@router.get(
    "/connection",
    response_model=AIConnectionStatus | AIConnectionNotConfigured,
)
def get_connection(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIConnectionStatus | AIConnectionNotConfigured:
    connection_status = ai_connection_service.get_connection_status(db, user.id)
    if connection_status is None:
        return AIConnectionNotConfigured()
    return {"configured": True, **connection_status}


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    ai_connection_service.delete_connection(db, user.id)
