"""
Admin Router - Internal administration endpoints.
Hidden from public API documentation.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status

from app.config import ADMIN_SECRET
from app.store import store


# Create router with internal prefix - hidden from schema
router = APIRouter(prefix="/internal", tags=["admin"])


async def validate_admin_secret(
    x_admin_secret: Optional[str] = Header(None, alias="X-ADMIN-SECRET")
) -> str:
    """
    Validate the admin secret header.
    Raises 401 if secret is missing or invalid.
    """
    if x_admin_secret is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin secret. Please provide X-ADMIN-SECRET header.",
        )
    
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin secret.",
        )
    
    return x_admin_secret


@router.post(
    "/apikeys/create",
    include_in_schema=False,  # Hide from OpenAPI documentation
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    x_admin_secret: Optional[str] = Header(None, alias="X-ADMIN-SECRET")
):
    """
    Create a new API key (hidden endpoint).
    
    Requires X-ADMIN-SECRET header for authentication.
    Generates a new UUID4-based API key and adds it to the store.
    """
    # Validate admin secret
    await validate_admin_secret(x_admin_secret)
    
    # Generate new API key using UUID4
    new_key = f"sk-synthquant-{uuid.uuid4().hex[:16]}"
    
    # Add to store
    store.add_key(new_key)
    
    # Generate timestamp
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    return {
        "new_key": new_key,
        "created_at": created_at,
        "note": "Save this, it will not be shown again.",
    }
